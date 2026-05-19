import { Router, type Request, type Response } from "express";
import {
  CategoryEnum,
  PriorityEnum,
  StatusEnum,
  TicketCreateSchema,
  TicketUpdateSchema
} from "../models/ticket.schema";
import * as store from "../store/ticketStore";
import { classify } from "../classifier/classifier";
import { logDecision } from "../classifier/log";
import { dispatch } from "../importers";
import { upload } from "../middleware/upload";
import { HttpError, asyncHandler } from "../utils/http";

export const ticketsRouter = Router();

function wantsAutoClassify(req: Request): boolean {
  const q = req.query.autoClassify;
  if (typeof q === "string" && (q === "true" || q === "1")) return true;
  if (req.body && typeof req.body === "object" && (req.body as { autoClassify?: unknown }).autoClassify === true) {
    return true;
  }
  return false;
}

ticketsRouter.post(
  "/",
  asyncHandler(async (req, res) => {
    const auto = wantsAutoClassify(req);
    const body = { ...(req.body as Record<string, unknown>) };
    delete body.autoClassify;
    const input = TicketCreateSchema.parse(body);
    const ticket = store.create(input);

    if (auto) {
      const result = classify(ticket);
      const finalCategory = input.category ?? result.category;
      const finalPriority = input.priority ?? result.priority;
      const manualOverride = input.category !== undefined || input.priority !== undefined;
      const updated = store.replaceClassification(ticket.id, {
        category: finalCategory,
        priority: finalPriority,
        classification: result
      });
      logDecision({ ticket_id: ticket.id, result, manual_override: manualOverride });
      res.status(201).json(updated);
      return;
    }
    res.status(201).json(ticket);
  })
);

ticketsRouter.post(
  "/import",
  upload.single("file"),
  asyncHandler(async (req, res) => {
    const file = req.file;
    if (!file) throw new HttpError(400, "file is required (multipart field 'file')");
    const auto = wantsAutoClassify(req);

    const result = dispatch(file.buffer, file.mimetype, file.originalname);
    const created = result.records.map((rec) => {
      const ticket = store.create(rec);
      if (auto) {
        const c = classify(ticket);
        const finalCategory = rec.category ?? c.category;
        const finalPriority = rec.priority ?? c.priority;
        const manualOverride = rec.category !== undefined || rec.priority !== undefined;
        const updated = store.replaceClassification(ticket.id, {
          category: finalCategory,
          priority: finalPriority,
          classification: c
        });
        logDecision({ ticket_id: ticket.id, result: c, manual_override: manualOverride });
        return updated ?? ticket;
      }
      return ticket;
    });

    res.status(200).json({
      total: result.total,
      successful: result.successful,
      failed: result.failed,
      tickets: created
    });
  })
);

ticketsRouter.get(
  "/",
  asyncHandler(async (req, res) => {
    const { category, priority, status, assigned_to, customer_id } = req.query;
    const filters: store.ListFilters = {};
    if (typeof category === "string") filters.category = CategoryEnum.parse(category);
    if (typeof priority === "string") filters.priority = PriorityEnum.parse(priority);
    if (typeof status === "string") filters.status = StatusEnum.parse(status);
    if (typeof assigned_to === "string") filters.assigned_to = assigned_to;
    if (typeof customer_id === "string") filters.customer_id = customer_id;

    const tickets = store.list(filters);
    res.json({ count: tickets.length, tickets });
  })
);

ticketsRouter.get(
  "/:id",
  asyncHandler(async (req, res) => {
    const ticket = store.getById(req.params.id);
    if (!ticket) throw new HttpError(404, "ticket not found");
    res.json(ticket);
  })
);

ticketsRouter.put(
  "/:id",
  asyncHandler(async (req, res) => {
    const patch = TicketUpdateSchema.parse(req.body);
    const updated = store.update(req.params.id, patch);
    if (!updated) throw new HttpError(404, "ticket not found");
    res.json(updated);
  })
);

ticketsRouter.delete(
  "/:id",
  asyncHandler(async (req, res) => {
    const ok = store.remove(req.params.id);
    if (!ok) throw new HttpError(404, "ticket not found");
    res.status(204).send();
  })
);

ticketsRouter.post(
  "/:id/auto-classify",
  asyncHandler(async (req, res) => {
    const ticket = store.getById(req.params.id);
    if (!ticket) throw new HttpError(404, "ticket not found");
    const result = classify(ticket);
    const updated = store.replaceClassification(ticket.id, {
      category: result.category,
      priority: result.priority,
      classification: result
    });
    logDecision({ ticket_id: ticket.id, result });
    res.json({ ticket: updated, classification: result });
  })
);

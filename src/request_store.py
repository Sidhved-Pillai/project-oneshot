import datetime as dt
import json
import os
import uuid
from pathlib import Path

import pandas as pd
from sqlalchemy import (
    Boolean, Column, Date, DateTime, Integer, LargeBinary, MetaData, Numeric,
    String, Table, Text, create_engine, delete, false, func, insert, inspect, select, text, update,
)

from .config import DATA
from .dtr_generator import DTR_COLUMNS


metadata = MetaData()
requests = Table(
    "dtr_requests",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("request_number", String(40), unique=True, index=True),
    Column("report_scope", String(20), nullable=False, default="DTR", server_default="DTR", index=True),
    Column("rtgs_data", Text, nullable=False, default="{}", server_default="{}"),
    Column("dtr_data", Text, nullable=False, default="{}", server_default="{}"),
    Column("batch_id", String(40), nullable=True, index=True),
    Column("trip_date", Date, nullable=False, index=True),
    Column("vehicle_number", String(40), nullable=False),
    Column("vehicle_type", String(80), default=""),
    Column("ownership_type", String(40), default=""),
    Column("from_location", String(160), default=""),
    Column("to_location", String(160), default=""),
    Column("company_name", String(200), default=""),
    Column("branch", String(160), default=""),
    Column("invoice_number", String(120), default=""),
    Column("beneficiary_name", String(200), default=""),
    Column("transporter_name", String(200), default=""),
    Column("expense_type", String(80), default=""),
    Column("amount", Numeric(14, 2), default=0),
    Column("payment_mode", String(80), default=""),
    Column("diesel_quantity", Numeric(14, 2), nullable=True),
    Column("revenue", Numeric(14, 2), default=0),
    Column("transporter_freight", Numeric(14, 2), default=0),
    Column("rtgs_advance", Numeric(14, 2), default=0),
    Column("cash_advance", Numeric(14, 2), default=0),
    Column("upi", Numeric(14, 2), default=0),
    Column("diesel_advance", Numeric(14, 2), default=0),
    Column("total_advance", Numeric(14, 2), default=0),
    Column("balance_amount", Numeric(14, 2), default=0),
    Column("payment", Numeric(14, 2), default=0),
    Column("status", String(30), default="Submitted", index=True),
    Column("notes", Text, default=""),
    Column("source_filename", String(255), default=""),
    Column("source_mime_type", String(100), default=""),
    Column("source_image", LargeBinary, nullable=True),
    Column("created_by", String(120), default=""),
    Column("created_at", DateTime, nullable=False, server_default=func.now()),
    Column("updated_at", DateTime, nullable=False, server_default=func.now()),
    Column("is_archived", Boolean, nullable=False, default=False, server_default=false()),
)

intake_batches = Table(
    "intake_batches", metadata,
    Column("batch_id", String(40), primary_key=True),
    Column("mode", String(20), nullable=False),
    Column("operator_name", String(120), default=""),
    Column("operator_prompt", Text, default=""),
    Column("ai_draft", Text, nullable=False, default="[]", server_default="[]"),
    Column("ai_summary", Text, default=""),
    Column("model_name", String(80), default=""),
    Column("request_label", String(60), unique=True, index=True),
    Column("dtr_workflow_status", String(30), nullable=False, default="Pending", server_default="Pending", index=True),
    Column("created_at", DateTime, nullable=False, server_default=func.now()),
    Column("updated_at", DateTime, nullable=False, server_default=func.now()),
)

request_attachments = Table(
    "request_attachments", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("batch_id", String(40), nullable=False, index=True),
    Column("filename", String(255), nullable=False),
    Column("mime_type", String(100), default=""),
    Column("payload", LargeBinary, nullable=False),
)

record_revisions = Table(
    "record_revisions", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("request_number", String(40), nullable=False, index=True),
    Column("batch_id", String(40), nullable=True, index=True),
    Column("report_scope", String(20), nullable=False),
    Column("snapshot", Text, nullable=False),
    Column("change_source", String(40), default="manual"),
    Column("edited_by", String(120), default=""),
    Column("created_at", DateTime, nullable=False, server_default=func.now()),
)


def database_url():
    """Use a durable hosted database when configured; SQLite is local-only."""
    return os.getenv("DATABASE_URL") or f"sqlite:///{Path(DATA) / 'project_oneshot.db'}"


class RequestStore:
    def __init__(self, url=None):
        url = url or database_url()
        if url.startswith("postgres://"):
            url = "postgresql+psycopg://" + url.removeprefix("postgres://")
        elif url.startswith("postgresql://"):
            url = "postgresql+psycopg://" + url.removeprefix("postgresql://")
        kwargs = {"pool_pre_ping": True}
        if url.startswith("sqlite"):
            kwargs["connect_args"] = {"check_same_thread": False}
        self.url = url
        self.engine = create_engine(url, **kwargs)
        metadata.create_all(self.engine)
        self._migrate_existing_database()

    def _migrate_existing_database(self):
        """Keep databases created by the first release compatible in place."""
        columns = {column["name"] for column in inspect(self.engine).get_columns("dtr_requests")}
        additions = {
            "report_scope": "VARCHAR(20) NOT NULL DEFAULT 'DTR'",
            "rtgs_data": "TEXT NOT NULL DEFAULT '{}'",
            "dtr_data": "TEXT NOT NULL DEFAULT '{}'",
            "batch_id": "VARCHAR(40)",
        }
        with self.engine.begin() as conn:
            for name, definition in additions.items():
                if name not in columns:
                    conn.execute(text(f"ALTER TABLE dtr_requests ADD COLUMN {name} {definition}"))
        batch_columns = {column["name"] for column in inspect(self.engine).get_columns("intake_batches")}
        batch_additions = {
            "ai_draft": "TEXT NOT NULL DEFAULT '[]'",
            "ai_summary": "TEXT",
            "model_name": "VARCHAR(80)",
            "request_label": "VARCHAR(60)",
            "dtr_workflow_status": "VARCHAR(30) NOT NULL DEFAULT 'Pending'",
            "updated_at": "TIMESTAMP",
        }
        with self.engine.begin() as conn:
            for name, definition in batch_additions.items():
                if name not in batch_columns:
                    conn.execute(text(f"ALTER TABLE intake_batches ADD COLUMN {name} {definition}"))

    @property
    def is_durable_cloud(self):
        return not self.url.startswith("sqlite")

    @staticmethod
    def _clean_values(values):
        clean = {key: value for key, value in values.items() if key in requests.c and key not in {"id", "request_number"}}
        for field in ("rtgs_data", "dtr_data"):
            if isinstance(clean.get(field), dict):
                clean[field] = json.dumps(clean[field], default=str)
        return clean

    def create(self, values):
        clean = self._clean_values(values)
        with self.engine.begin() as conn:
            result = conn.execute(insert(requests).values(**clean))
            row_id = result.inserted_primary_key[0]
            number = f"REQ-{values['trip_date']:%Y%m}-{row_id:06d}"
            conn.execute(update(requests).where(requests.c.id == row_id).values(request_number=number))
            self._insert_revision(conn, number, clean, "initial", clean.get("created_by", ""))
        return number

    def create_many(self, values_list):
        numbers = []
        with self.engine.begin() as conn:
            for values in values_list:
                result = conn.execute(insert(requests).values(**self._clean_values(values)))
                row_id = result.inserted_primary_key[0]
                number = f"REQ-{values['trip_date']:%Y%m}-{row_id:06d}"
                conn.execute(update(requests).where(requests.c.id == row_id).values(request_number=number))
                self._insert_revision(conn, number, self._clean_values(values), "initial", values.get("created_by", ""))
                numbers.append(number)
        return numbers

    def sync_batch_records(self, batch_id, report_scope, values_list, edited_by="", change_source="manual"):
        """Atomically update/add rows; removed editor rows are retained as Cancelled."""
        numbers = []
        with self.engine.begin() as conn:
            existing = [dict(row) for row in conn.execute(
                select(requests).where(
                    requests.c.batch_id == batch_id, requests.c.report_scope == report_scope,
                    requests.c.status != "Cancelled",
                ).order_by(requests.c.id)
            ).mappings()]
            for index, values in enumerate(values_list):
                clean = self._clean_values({**values, "batch_id": batch_id, "report_scope": report_scope})
                clean["updated_at"] = dt.datetime.now()
                if index < len(existing):
                    number = existing[index]["request_number"]
                    conn.execute(update(requests).where(requests.c.request_number == number).values(**clean))
                    row = conn.execute(select(requests).where(requests.c.request_number == number)).mappings().first()
                    self._insert_revision(conn, number, dict(row), change_source, edited_by)
                else:
                    result = conn.execute(insert(requests).values(**clean))
                    row_id = result.inserted_primary_key[0]
                    number = f"REQ-{values['trip_date']:%Y%m}-{row_id:06d}"
                    conn.execute(update(requests).where(requests.c.id == row_id).values(request_number=number))
                    row = conn.execute(select(requests).where(requests.c.id == row_id)).mappings().first()
                    self._insert_revision(conn, number, dict(row), change_source, edited_by)
                numbers.append(number)
            for old in existing[len(values_list):]:
                conn.execute(update(requests).where(requests.c.id == old["id"]).values(
                    status="Cancelled", updated_at=dt.datetime.now(),
                ))
                old["status"] = "Cancelled"
                self._insert_revision(conn, old["request_number"], old, change_source, edited_by)
        return numbers

    def update(self, request_number, values, change_source="manual", edited_by=""):
        clean = {key: value for key, value in values.items() if key in requests.c and key not in {"id", "request_number", "created_at"}}
        for field in ("rtgs_data", "dtr_data"):
            if isinstance(clean.get(field), dict):
                clean[field] = json.dumps(clean[field], default=str)
        clean["updated_at"] = dt.datetime.now()
        with self.engine.begin() as conn:
            conn.execute(update(requests).where(requests.c.request_number == request_number).values(**clean))
            row = conn.execute(select(requests).where(requests.c.request_number == request_number)).mappings().first()
            if row:
                self._insert_revision(conn, request_number, dict(row), change_source, edited_by or clean.get("created_by", ""))

    @staticmethod
    def _revision_snapshot(values):
        excluded = {"source_image"}
        return json.dumps({key: value for key, value in values.items() if key not in excluded}, default=str)

    def _insert_revision(self, conn, request_number, values, change_source, edited_by):
        conn.execute(insert(record_revisions).values(
            request_number=request_number, batch_id=values.get("batch_id"),
            report_scope=values.get("report_scope", ""), snapshot=self._revision_snapshot(values),
            change_source=change_source, edited_by=edited_by,
        ))

    def get(self, request_number):
        with self.engine.connect() as conn:
            row = conn.execute(select(requests).where(requests.c.request_number == request_number)).mappings().first()
        return dict(row) if row else None

    def create_batch(self, mode, operator_name, operator_prompt, attachments, ai_draft=None, ai_summary="", model_name="gemini-3.6-flash"):
        batch_id = f"BATCH-{uuid.uuid4().hex[:16].upper()}"
        created = dt.datetime.now()
        base_label = f"RTGS- Record-{created:%d/%m/%y}"
        with self.engine.begin() as conn:
            existing = conn.execute(select(func.count()).select_from(intake_batches).where(
                intake_batches.c.request_label.like(f"{base_label}%")
            )).scalar() or 0
            request_label = base_label if not existing else f"{base_label} ({existing + 1})"
            conn.execute(insert(intake_batches).values(
                batch_id=batch_id, mode=mode, operator_name=operator_name,
                operator_prompt=operator_prompt, ai_draft=json.dumps(ai_draft or [], default=str),
                ai_summary=ai_summary, model_name=model_name, request_label=request_label,
                dtr_workflow_status="Pending", updated_at=dt.datetime.now(),
            ))
            for attachment in attachments:
                conn.execute(insert(request_attachments).values(
                    batch_id=batch_id, filename=attachment["filename"],
                    mime_type=attachment["mime_type"], payload=attachment["data"],
                ))
        return batch_id

    def add_attachments(self, batch_id, attachments):
        with self.engine.begin() as conn:
            for attachment in attachments:
                conn.execute(insert(request_attachments).values(
                    batch_id=batch_id, filename=attachment["filename"],
                    mime_type=attachment.get("mime_type", ""), payload=attachment["data"],
                ))
        return len(attachments)

    def get_batch(self, batch_id):
        with self.engine.connect() as conn:
            row = conn.execute(select(intake_batches).where(intake_batches.c.batch_id == batch_id)).mappings().first()
        return dict(row) if row else None

    def list_batches(self, dtr_status=None):
        query = select(intake_batches)
        if dtr_status:
            query = query.where(intake_batches.c.dtr_workflow_status == dtr_status)
        query = query.order_by(intake_batches.c.created_at.desc())
        with self.engine.connect() as conn:
            batches = [dict(row) for row in conn.execute(query).mappings()]
            for batch in batches:
                counts = conn.execute(
                    select(requests.c.report_scope, func.count())
                    .where(requests.c.batch_id == batch["batch_id"], requests.c.status != "Cancelled")
                    .group_by(requests.c.report_scope)
                ).all()
                batch["row_counts"] = dict(counts)
        return batches

    def get_batch_requests(self, batch_id, report_scope, include_cancelled=False):
        query = select(requests).where(requests.c.batch_id == batch_id, requests.c.report_scope == report_scope)
        if not include_cancelled:
            query = query.where(requests.c.status != "Cancelled")
        query = query.order_by(requests.c.id)
        with self.engine.connect() as conn:
            return [dict(row) for row in conn.execute(query).mappings()]

    def set_batch_dtr_status(self, batch_id, status):
        with self.engine.begin() as conn:
            conn.execute(update(intake_batches).where(intake_batches.c.batch_id == batch_id).values(
                dtr_workflow_status=status, updated_at=dt.datetime.now(),
            ))

    def delete_batch(self, batch_id):
        """Permanent deletion. Call only after explicit user confirmation."""
        with self.engine.begin() as conn:
            conn.execute(delete(record_revisions).where(record_revisions.c.batch_id == batch_id))
            conn.execute(delete(request_attachments).where(request_attachments.c.batch_id == batch_id))
            deleted_rows = conn.execute(delete(requests).where(requests.c.batch_id == batch_id)).rowcount
            deleted_batch = conn.execute(delete(intake_batches).where(intake_batches.c.batch_id == batch_id)).rowcount
        return {"requests": deleted_rows, "batches": deleted_batch}

    def get_attachments(self, batch_id):
        if not batch_id:
            return []
        with self.engine.connect() as conn:
            rows = conn.execute(
                select(request_attachments).where(request_attachments.c.batch_id == batch_id)
                .order_by(request_attachments.c.id)
            ).mappings()
            return [dict(row) for row in rows]

    def find_duplicate(self, trip_date, vehicle_number, invoice_number, amount):
        conditions = [requests.c.trip_date == trip_date, requests.c.vehicle_number == vehicle_number]
        if invoice_number:
            conditions.append(requests.c.invoice_number == invoice_number)
        else:
            conditions.append(requests.c.amount == amount)
        with self.engine.connect() as conn:
            return conn.execute(select(requests.c.request_number).where(*conditions).limit(1)).scalar()

    def list(self, start_date=None, end_date=None, status=None, include_archived=False, report_kind=None):
        query = select(requests)
        if start_date:
            query = query.where(requests.c.trip_date >= start_date)
        if end_date:
            query = query.where(requests.c.trip_date <= end_date)
        if status == "All active":
            query = query.where(requests.c.status != "Cancelled")
        elif status and status != "All":
            query = query.where(requests.c.status == status)
        if not include_archived:
            query = query.where(requests.c.is_archived.is_(False))
        if report_kind:
            query = query.where(requests.c.report_scope.in_([report_kind, "Both"]))
        query = query.order_by(requests.c.trip_date.desc(), requests.c.id.desc())
        with self.engine.connect() as conn:
            return [dict(row) for row in conn.execute(query).mappings()]

    def archive_before(self, cutoff):
        with self.engine.begin() as conn:
            result = conn.execute(
                update(requests)
                .where(requests.c.trip_date < cutoff, requests.c.is_archived.is_(False))
                .values(is_archived=True, updated_at=dt.datetime.now())
            )
        return result.rowcount


def rows_to_dtr(rows):
    records = []
    for i, row in enumerate(rows, 1):
        record = {column: "" for column in DTR_COLUMNS}
        record.update({
            "Sr No.": i, "Branch": row["branch"], "Compnay Name": row["company_name"],
            "Date": row["trip_date"], "Vehicle No.": row["vehicle_number"],
            "Vehicle Type": row["vehicle_type"], "Own/Outside Vehicle": row["ownership_type"],
            "From": row["from_location"], "Invoice No.": row["invoice_number"], "To": row["to_location"],
            "Revenue": row["revenue"], "Transporter Freight": row["transporter_freight"],
            "RTGS ADVANCE": row["rtgs_advance"], "Cash Adv.": row["cash_advance"], "UPI": row["upi"],
            "Diesel Qty": row["diesel_quantity"], "Diesel Adv.": row["diesel_advance"],
            "Total Adv.": row["total_advance"], "Balance Amt.": row["balance_amount"],
            "Payment": row["payment"], "Benificiary Name": row["beneficiary_name"],
            "Transporter Name": row["transporter_name"],
        })
        records.append(record)
    return pd.DataFrame(records, columns=DTR_COLUMNS)

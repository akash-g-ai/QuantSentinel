"""QuantSentinel FastAPI Backend.

This module provides a REST API for the QuantSentinel data validation system.
It imports and reuses all existing validation logic from src/quantsentinel/.

Endpoints:
- GET /api/health - Health check
- GET /api/datasets/demo - Get demo dataset info
- GET /api/datasets/demo/metadata - Get demo dataset metadata
- POST /api/datasets/upload - Upload a CSV file
- POST /api/validation/run - Run validation on a dataset
- GET /api/validation/{run_id} - Get validation results
- GET /api/history - Get validation history
- GET /api/reports/{run_id}/json - Get JSON report
- GET /api/reports/{run_id}/csv - Get CSV findings report
- GET /api/reports/{run_id}/txt - Get text summary
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

# Ensure src/ is on the path (work from project root)
_PROJECT_ROOT = Path(__file__).parent.parent
_SRC = _PROJECT_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from quantsentinel.audit import AuditDatabase
from quantsentinel.ingestion import IngestionError, load_csv
from quantsentinel.models import ValidationStatus
import pandas as pd
from quantsentinel.pipeline import PipelineStageError, run_pipeline
from quantsentinel.quality import AssessedReport
from quantsentinel.reporting import build_text_summary, to_csv, to_json

# Constants
_DB_PATH = Path(__file__).parent.parent / "data" / "audit.db"
_DEMO_PATH = Path(__file__).parent.parent / "data" / "raw" / "INFY_NS_2024.csv"
_MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10MB

# FastAPI app
app = FastAPI(
    title="QuantSentinel API",
    description="Financial Market Data Quality Validation API",
    version="1.0.0",
)

# CORS middleware for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
    }


@app.get("/api/datasets/demo")
async def get_demo_dataset() -> dict[str, Any]:
    """Get demo dataset information."""
    if not _DEMO_PATH.exists():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Demo dataset not found. Please check data/raw/INFY_NS_2024.csv",
        )

    return {
        "name": "INFY.NS (Infosys) 2024",
        "path": str(_DEMO_PATH),
        "size_bytes": _DEMO_PATH.stat().st_size,
        "exists": True,
    }


@app.get("/api/datasets/demo/metadata")
async def get_demo_dataset_metadata() -> dict[str, Any]:
    """Get demo dataset metadata including preview and statistics."""
    if not _DEMO_PATH.exists():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Demo dataset not found",
        )

    try:
        df = load_csv(_DEMO_PATH)

        return {
            "name": "INFY.NS (Infosys) 2024",
            "records": len(df),
            "columns": list(df.columns),
            "date_range": {
                "start": str(df["Date"].min()),
                "end": str(df["Date"].max()),
            },
            "price_range": {
                "low": float(df["Low"].min()),
                "high": float(df["High"].max()),
                "open_start": float(df["Open"].iloc[0]),
                "close_end": float(df["Close"].iloc[-1]),
            },
            "volume_stats": {
                "mean": float(df["Volume"].mean()),
                "max": float(df["Volume"].max()),
                "sum": float(df["Volume"].sum()),
            },
            "preview": df.head(10).to_dict(orient="records"),
        }
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load demo dataset: {str(exc)}",
        ) from exc


@app.get("/api/chart/data")
async def get_chart_data() -> dict[str, Any]:
    """Get chart-ready OHLCV data for visualization."""
    if not _DEMO_PATH.exists():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Demo dataset not found",
        )

    try:
        df = load_csv(_DEMO_PATH)
        
        # Ensure correct column order
        columns = ['Date', 'Open', 'High', 'Low', 'Close', 'Volume']
        
        # Map columns if names differ (case-insensitive)
        column_map = {col.lower(): col for col in df.columns}
        mapped_df = pd.DataFrame()
        for col in columns:
            if col.lower() in column_map:
                mapped_df[col] = df[column_map[col.lower()]]
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Missing required column: {col}",
                )
        
        return {
            "data": mapped_df.to_dict(orient="records"),
            "metadata": {
                "name": "INFY.NS (Infosys) 2024",
                "records": len(mapped_df),
                "date_range": {
                    "start": str(mapped_df["Date"].min()),
                    "end": str(mapped_df["Date"].max()),
                },
                "price_range": {
                    "min": float(mapped_df["Low"].min()),
                    "max": float(mapped_df["High"].max()),
                },
                "volume_stats": {
                    "mean": float(mapped_df["Volume"].mean()),
                    "max": float(mapped_df["Volume"].max()),
                },
            },
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load chart data: {str(exc)}",
        ) from exc


@app.post("/api/datasets/upload")
async def upload_dataset(file: UploadFile = File(...)) -> dict[str, Any]:
    """Upload a CSV dataset for validation."""
    # Validate file type
    if not file.filename.endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only CSV files are allowed",
        )

    # Validate file size
    file.file.seek(0, 2)  # Seek to end
    file_size = file.file.tell()
    file.file.seek(0)  # Reset to beginning

    if file_size > _MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_PAYLOAD_TOO_LARGE,
            detail=f"File too large. Maximum size is {_MAX_UPLOAD_SIZE / 1024 / 1024}MB",
        )

    # Save uploaded file to temp file
    try:
        with NamedTemporaryFile(
            suffix=".csv",
            delete=False,
            dir=Path(__file__).parent / "data" / "raw",
        ) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = Path(tmp.name)

        return {
            "success": True,
            "filename": file.filename,
            "path": str(tmp_path),
            "size_bytes": file_size,
            "message": "File uploaded successfully",
        }
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save uploaded file: {str(exc)}",
        ) from exc


@app.post("/api/validation/run")
async def run_validation(
    dataset_path: str | None = None,
    dataset_name: str | None = None,
) -> dict[str, Any]:
    """Run the full validation pipeline on a dataset."""
    # Determine the path
    if dataset_path is None:
        # Use demo dataset if no path provided
        if not _DEMO_PATH.exists():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Demo dataset not found",
            )
        dataset_path = str(_DEMO_PATH)
        dataset_name = dataset_name or "INFY.NS (Infosys) 2024"
    else:
        dataset_name = dataset_name or Path(dataset_path).name

    try:
        assessed: AssessedReport = run_pipeline(dataset_path)

        # Save to audit database
        with AuditDatabase(_DB_PATH) as db:
            run_id = db.record_run(assessed)

        return {
            "success": True,
            "run_id": run_id,
            "dataset_name": dataset_name,
            "dataset_path": dataset_path,
            "assessment": {
                "score": assessed.assessment.score,
                "overall_status": assessed.assessment.overall_status.name,
                "summary": assessed.assessment.summary,
                "status_counts": {
                    "total": assessed.assessment.status_counts.total,
                    "fail_count": assessed.assessment.status_counts.fail_count,
                    "warning_count": assessed.assessment.status_counts.warning_count,
                    "pass_count": assessed.assessment.status_counts.pass_count,
                },
            },
            "report": {
                "dataset_name": assessed.report.dataset_name,
                "stage_results": [
                    {
                        "stage_name": s.stage_name,
                        "status": s.status.name,
                        "finding_count": s.finding_count,
                        "findings": [
                            {
                                "rule_id": f.rule_id,
                                "status": f.status.name,
                                "message": f.message,
                                "affected_rows": f.affected_rows,
                                "metadata": f.metadata,
                            }
                            for f in s.findings
                        ],
                    }
                    for s in assessed.report.stage_results
                ],
            },
            "timestamp": datetime.utcnow().isoformat(),
        }
    except IngestionError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ingestion error: {str(exc)}",
        ) from exc
    except PipelineStageError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Pipeline stage error in {exc.stage_name}: {str(exc.original)}",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Validation failed: {str(exc)}",
        ) from exc


@app.get("/api/validation/{run_id}")
async def get_validation_result(run_id: str) -> dict[str, Any]:
    """Get validation results by run ID."""
    try:
        with AuditDatabase(_DB_PATH) as db:
            run_record = db.get_run(run_id)
            if run_record is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Run not found: {run_id}",
                )

            stage_records = db.get_stage_results(run_id)
            finding_records = db.get_findings(run_id)

        return {
            "success": True,
            "run_id": run_id,
            "dataset_name": run_record.dataset_name,
            "timestamp": run_record.recorded_at,
            "assessment": {
                "score": run_record.quality_score,
                "overall_status": run_record.overall_status,
                "summary": run_record.summary,
                "status_counts": {
                    "total": run_record.total_findings,
                    "fail_count": run_record.fail_count,
                    "warning_count": run_record.warning_count,
                    "pass_count": run_record.pass_count,
                },
            },
            "stages": [
                {
                    "stage_name": s.stage_name,
                    "status": s.status,
                    "finding_count": s.finding_count,
                }
                for s in stage_records
            ],
            "findings": [
                {
                    "rule_id": f.rule_id,
                    "status": f.status,
                    "message": f.message,
                    "affected_row_count": f.affected_row_count,
                }
                for f in finding_records
            ],
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve validation result: {str(exc)}",
        ) from exc


@app.get("/api/history")
async def get_validation_history() -> dict[str, Any]:
    """Get validation history."""
    try:
        with AuditDatabase(_DB_PATH) as db:
            runs = db.list_runs()

        return {
            "success": True,
            "total": len(runs),
            "runs": [
                {
                    "run_id": r.run_id,
                    "dataset_name": r.dataset_name,
                    "recorded_at": r.recorded_at,
                    "quality_score": r.quality_score,
                    "overall_status": r.overall_status,
                    "total_findings": r.total_findings,
                    "fail_count": r.fail_count,
                    "warning_count": r.warning_count,
                    "pass_count": r.pass_count,
                }
                for r in runs
            ],
        }
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve history: {str(exc)}",
        ) from exc


@app.get("/api/reports/{run_id}/json")
async def get_json_report(run_id: str) -> Response:
    """Get JSON report for a validation run."""
    try:
        with AuditDatabase(_DB_PATH) as db:
            run_record = db.get_run(run_id)
            if run_record is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Run not found: {run_id}",
                )

            assessed = AssessedReport(
                dataset_name=run_record.dataset_name,
                assessment=type("Assessment", (), {
                    "score": run_record.quality_score,
                    "overall_status": ValidationStatus(run_record.overall_status.lower()),
                    "summary": run_record.summary,
                    "status_counts": type("Counts", (), {
                        "total": run_record.total_findings,
                        "fail_count": run_record.fail_count,
                        "warning_count": run_record.warning_count,
                        "pass_count": run_record.pass_count,
                    })(),
                })(),
                report=type("Report", (), {
                    "dataset_name": run_record.dataset_name,
                    "stage_results": [],
                })(),
            )

            # Reconstruct report from stage and finding records
            stage_records = db.get_stage_results(run_id)
            finding_records = db.get_findings(run_id)

            stages = []
            for s in stage_records:
                stage_findings = [
                    type("Finding", (), {
                        "rule_id": f.rule_id,
                        "status": ValidationStatus(f.status.lower()),
                        "message": f.message,
                        "affected_rows": [int(r) for r in f.affected_rows.split(",") if r],
                        "metadata": {},
                    })()
                    for f in finding_records if f.stage_name == s.stage_name
                ]
                stages.append(
                    type("StageResult", (), {
                        "stage_name": s.stage_name,
                        "status": ValidationStatus(s.status.lower()),
                        "findings": stage_findings,
                        "finding_count": s.finding_count,
                    })()
                )

            assessed.report = type("Report", (), {
                "dataset_name": run_record.dataset_name,
                "stage_results": stages,
            })()

            json_content = to_json(assessed)

        return Response(
            content=json_content,
            media_type="application/json",
            headers={
                "Content-Disposition": f'attachment; filename="{run_record.dataset_name}_validation.json"',
            },
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate JSON report: {str(exc)}",
        ) from exc


@app.get("/api/reports/{run_id}/csv")
async def get_csv_report(run_id: str) -> Response:
    """Get CSV findings report for a validation run."""
    try:
        with AuditDatabase(_DB_PATH) as db:
            run_record = db.get_run(run_id)
            if run_record is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Run not found: {run_id}",
                )

            assessed = AssessedReport(
                dataset_name=run_record.dataset_name,
                assessment=type("Assessment", (), {
                    "score": run_record.quality_score,
                    "overall_status": ValidationStatus(run_record.overall_status.lower()),
                    "summary": run_record.summary,
                    "status_counts": type("Counts", (), {
                        "total": run_record.total_findings,
                        "fail_count": run_record.fail_count,
                        "warning_count": run_record.warning_count,
                        "pass_count": run_record.pass_count,
                    })(),
                })(),
                report=type("Report", (), {
                    "dataset_name": run_record.dataset_name,
                    "stage_results": [],
                })(),
            )

            # Reconstruct report from stage and finding records
            stage_records = db.get_stage_results(run_id)
            finding_records = db.get_findings(run_id)

            stages = []
            for s in stage_records:
                stage_findings = [
                    type("Finding", (), {
                        "rule_id": f.rule_id,
                        "status": ValidationStatus(f.status.lower()),
                        "message": f.message,
                        "affected_rows": [int(r) for r in f.affected_rows.split(",") if r],
                        "metadata": {},
                    })()
                    for f in finding_records if f.stage_name == s.stage_name
                ]
                stages.append(
                    type("StageResult", (), {
                        "stage_name": s.stage_name,
                        "status": ValidationStatus(s.status.lower()),
                        "findings": stage_findings,
                        "finding_count": s.finding_count,
                    })()
                )

            assessed.report = type("Report", (), {
                "dataset_name": run_record.dataset_name,
                "stage_results": stages,
            })()

            csv_content = to_csv(assessed)

        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="{run_record.dataset_name}_findings.csv"',
            },
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate CSV report: {str(exc)}",
        ) from exc


@app.get("/api/reports/{run_id}/txt")
async def get_txt_report(run_id: str) -> Response:
    """Get text summary report for a validation run."""
    try:
        with AuditDatabase(_DB_PATH) as db:
            run_record = db.get_run(run_id)
            if run_record is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Run not found: {run_id}",
                )

            assessed = AssessedReport(
                dataset_name=run_record.dataset_name,
                assessment=type("Assessment", (), {
                    "score": run_record.quality_score,
                    "overall_status": ValidationStatus(run_record.overall_status.lower()),
                    "summary": run_record.summary,
                    "status_counts": type("Counts", (), {
                        "total": run_record.total_findings,
                        "fail_count": run_record.fail_count,
                        "warning_count": run_record.warning_count,
                        "pass_count": run_record.pass_count,
                    })(),
                })(),
                report=type("Report", (), {
                    "dataset_name": run_record.dataset_name,
                    "stage_results": [],
                })(),
            )

            # Reconstruct report from stage and finding records
            stage_records = db.get_stage_results(run_id)
            finding_records = db.get_findings(run_id)

            stages = []
            for s in stage_records:
                stage_findings = [
                    type("Finding", (), {
                        "rule_id": f.rule_id,
                        "status": ValidationStatus(f.status.lower()),
                        "message": f.message,
                        "affected_rows": [int(r) for r in f.affected_rows.split(",") if r],
                        "metadata": {},
                    })()
                    for f in finding_records if f.stage_name == s.stage_name
                ]
                stages.append(
                    type("StageResult", (), {
                        "stage_name": s.stage_name,
                        "status": ValidationStatus(s.status.lower()),
                        "findings": stage_findings,
                        "finding_count": s.finding_count,
                    })()
                )

            assessed.report = type("Report", (), {
                "dataset_name": run_record.dataset_name,
                "stage_results": stages,
            })()

            txt_content = build_text_summary(assessed)

        return Response(
            content=txt_content,
            media_type="text/plain",
            headers={
                "Content-Disposition": f'attachment; filename="{run_record.dataset_name}_summary.txt"',
            },
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate text report: {str(exc)}",
        ) from exc

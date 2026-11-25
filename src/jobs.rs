//! Bounded asynchronous operation handles for agent clients with short tool timeouts.
use crate::engine::Engine;
use serde_json::{json, Value};
use std::{
    collections::BTreeMap,
    path::PathBuf,
    sync::{
        atomic::{AtomicBool, Ordering},
        Arc, Mutex,
    },
};
pub const COMMANDS: &[&str] = &[
    "wmts_rasters",
    "terrain_mesh",
    "si_run",
    "assist_explain",
    "assist_tags",
    "client_call",
    "open",
    "import_preview",
    "file_probe",
    "gis_load",
    "gis_import_preview",
    "import_validate",
    "import_review",
    "import_rejections_export",
    "import_commit",
    "analyze",
    "analysis_execute",
    "query",
    "display_data",
    "aggregate",
    "statistics",
    "field_profile",
    "pattern_scan",
    "analytics_run",
    "space_time_aggregate",
    "aggregate_apply",
    "save",
    "export",
];
pub type Jobs = Arc<Mutex<BTreeMap<String, Job>>>;
const RESULT_BUDGET: usize = 16 * 1024 * 1024;
const DEFAULT_RESULT_LIMIT: usize = 4 * 1024 * 1024;
pub struct Job {
    pub command: String,
    pub status: String,
    pub cancelled: Arc<AtomicBool>,
    pub progress: u64,
    pub sequence: u64,
    pub total: Option<u64>,
    pub message: String,
    pub result: Option<Value>,
    result_bytes: usize,
    pub receipt: Option<Value>,
    pub error: Option<String>,
    pub scope: Option<PathBuf>,
    pub created: String,
}
fn metadata(id: &str, job: &Job) -> Value {
    use crate::operation::{Phase, ProgressEvent};
    let phase = match job.status.as_str() {
        "queued" => Phase::Queued,
        "completed" => Phase::Completed,
        "cancelled" => Phase::Cancelled,
        "failed" => Phase::Failed,
        _ => {
            if job.message.starts_with("Committ") {
                Phase::Committing
            } else if job.message.starts_with("Reading") {
                Phase::Reading
            } else if job.message.starts_with("Staging") {
                Phase::Staging
            } else {
                Phase::Validating
            }
        }
    };
    let terminal = matches!(job.status.as_str(), "completed" | "cancelled" | "failed");
    let event = ProgressEvent {
        phase,
        completed: job.progress,
        total: job.total,
        unit: if job.message.contains("bytes") {
            "bytes"
        } else if job.message.contains("events") {
            "rows"
        } else if job.message.contains("SI") {
            "steps"
        } else {
            "items"
        },
        sequence: job.sequence + u64::from(terminal),
    };
    json!({"job_id":id,"command":job.command,"status":job.status,"progress":job.progress,"total":job.total,"message":job.message,"progress_event":event,"created":job.created,"has_result":job.result.is_some(),"cancel_requested":job.cancelled.load(Ordering::Relaxed),"commit_receipt":job.receipt,"error":job.error.as_ref().map(|e|json!({"code":crate::mcp::error_code(e),"message":e}))})
}
pub fn invoke(engine: &Engine, command: &str, args: Value) -> Result<Value, String> {
    if command == "job_start" {
        let command = args["command"].as_str().unwrap().to_owned();
        let arguments = args.get("arguments").cloned().unwrap_or(json!({}));
        if !COMMANDS.contains(&command.as_str()) {
            return Err("Invalid asynchronous job command".into());
        }
        crate::schema::validate(&command, &arguments)?;
        let scope = crate::operation::scope();
        let workspace = crate::operation::workspace()
            .map(Ok)
            .unwrap_or_else(|| engine.workspace_identity())?;
        let mut jobs = engine.jobs.lock().map_err(|_| "Job registry unavailable")?;
        if jobs
            .values()
            .filter(|j| matches!(j.status.as_str(), "queued" | "running"))
            .count()
            >= 16
        {
            return Err("RESOURCE_LIMIT: at most 16 queued/running jobs".into());
        }
        while jobs.len() >= 64 {
            let oldest = jobs
                .iter()
                .filter(|(_, j)| !matches!(j.status.as_str(), "queued" | "running"))
                .min_by_key(|(_, j)| &j.created)
                .map(|(id, _)| id.clone())
                .ok_or("Job registry is full")?;
            jobs.remove(&oldest);
        }
        // Reserve space before starting writes. A read completing concurrently
        // must never consume the space needed to report a committed operation.
        let result_limit = if command == "wmts_rasters" {
            8 * 1024 * 1024
        } else {
            DEFAULT_RESULT_LIMIT
        };
        let reserved =
            if crate::schema::is_mutation(&command, &arguments) || command == "analytics_run" {
                result_limit
            } else {
                0
            };
        if reserved > 0
            && jobs.values().map(|job| job.result_bytes).sum::<usize>() + reserved > RESULT_BUDGET
        {
            return Err("RESOURCE_LIMIT: insufficient job result space; release completed jobs before starting this operation".into());
        }
        let mut random = [0u8; 16];
        getrandom::fill(&mut random).map_err(|e| e.to_string())?;
        let id: String = random.iter().map(|b| format!("{b:02x}")).collect();
        let cancelled = Arc::new(AtomicBool::new(false));
        jobs.insert(
            id.clone(),
            Job {
                command: command.clone(),
                status: "queued".into(),
                cancelled: cancelled.clone(),
                progress: 0,
                sequence: 0,
                total: None,
                message: "Queued".into(),
                result: None,
                result_bytes: reserved,
                receipt: None,
                error: None,
                scope: scope.clone(),
                created: chrono::Utc::now().to_rfc3339(),
            },
        );
        let response = metadata(&id, jobs.get(&id).unwrap());
        drop(jobs);
        let engine = engine.clone();
        let job_id = id.clone();
        std::thread::spawn(move || {
            let registry = engine.jobs.clone();
            let progress_id = job_id.clone();
            let progress = Arc::new(move |value, total, message: &str| {
                if let Ok(mut jobs) = registry.lock() {
                    if let Some(job) = jobs.get_mut(&progress_id) {
                        job.status = "running".into();
                        job.sequence = job.sequence.saturating_add(1);
                        job.progress = value;
                        job.total = total;
                        job.message = message.into();
                    }
                }
            });
            let result = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| {
                crate::operation::with_context(
                    crate::operation::Context {
                        cancelled: cancelled.clone(),
                        progress: Some(progress),
                        scope,
                    },
                    || {
                        crate::operation::with_workspace(workspace, || {
                            engine.invoke(&command, arguments)
                        })
                    },
                )
            }))
            .unwrap_or_else(|_| Err("OPERATION_FAILED: background worker failed".into()));
            let chat_owned =
                command == "si_run" && engine.assistant.chat_finished(&job_id, &result);
            if let Ok(mut jobs) = engine.jobs.lock() {
                let retained: usize = jobs.values().map(|job| job.result_bytes).sum();
                if let Some(job) = jobs.get_mut(&job_id) {
                    let available = RESULT_BUDGET - (retained - job.result_bytes);
                    job.result_bytes = 0;
                    job.receipt = result
                        .as_ref()
                        .ok()
                        .and_then(|v| v.get("commit_receipt"))
                        .filter(|v| v.to_string().len() <= 4096)
                        .cloned();
                    match result {
                        Ok(value) => {
                            let bytes = value.to_string().len();
                            if bytes <= result_limit.min(available) {
                                job.status = "completed".into();
                                job.message = "Completed".into();
                                job.result_bytes = bytes;
                                job.result = Some(value);
                            } else {
                                job.status = "failed".into();
                                job.error=Some("RESOURCE_LIMIT: inspect commit_receipt before retrying; job results exceed 4 MiB per job (8 MiB for rasters) / 16 MiB retained; reduce query budgets or release completed jobs".into());
                            }
                        }
                        Err(e) => {
                            job.status = if crate::mcp::error_code(&e) == "CANCELLED" {
                                "cancelled"
                            } else {
                                "failed"
                            }
                            .into();
                            job.error = Some(e);
                        }
                    }
                }
                if chat_owned {
                    jobs.remove(&job_id);
                }
            }
        });
        return Ok(response);
    }
    let id = args["job_id"].as_str().unwrap();
    let mut jobs = engine.jobs.lock().map_err(|_| "Job registry unavailable")?;
    let job = jobs.get_mut(id).ok_or("Job not found or expired")?;
    if crate::operation::scope().is_some() && crate::operation::scope() != job.scope {
        return Err("Job is outside the current filesystem scope".into());
    }
    match command {
        "job_cancel" => {
            job.cancelled.store(true, Ordering::Relaxed);
            Ok(metadata(id, job))
        }
        "job_status" => Ok(metadata(id, job)),
        "job_result" => {
            let mut value = metadata(id, job);
            value["result"] = job.result.clone().unwrap_or(Value::Null);
            Ok(value)
        }
        "job_release" => {
            if matches!(job.status.as_str(), "queued" | "running") {
                return Err("CONFLICT: cancel and wait for the job before releasing it".into());
            }
            jobs.remove(id);
            Ok(json!({"released":true,"job_id":id}))
        }
        _ => Err("Unknown job operation".into()),
    }
}

from fastapi import APIRouter

from clothes_model.modules._stub import StubRoute, add_stub_routes

router = APIRouter(tags=["Jobs", "JobItems"])
add_stub_routes(
    router,
    (
        StubRoute("/api/v1/jobs", "GET", "listJobs"),
        StubRoute("/api/v1/jobs", "POST", "createJob"),
        StubRoute("/api/v1/jobs/{job_id}", "GET", "getJob"),
        StubRoute("/api/v1/jobs/{job_id}/cancel", "POST", "cancelJob"),
        StubRoute("/api/v1/job-items/{job_item_id}", "GET", "getJobItem"),
        StubRoute("/api/v1/job-items/{job_item_id}/cancel", "POST", "cancelJobItem"),
        StubRoute("/api/v1/job-items/{job_item_id}/retry", "POST", "retryJobItem"),
        StubRoute("/api/v1/job-items/{job_item_id}/requery", "POST", "requeryJobItem"),
        StubRoute(
            "/api/v1/job-items/{job_item_id}/finish-failed",
            "POST",
            "finishJobItemAsFailed",
        ),
    ),
)

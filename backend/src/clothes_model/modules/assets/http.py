from fastapi import APIRouter

from clothes_model.modules._stub import StubRoute, add_stub_routes

router = APIRouter(tags=["Assets", "Uploads"])
add_stub_routes(
    router,
    (
        StubRoute("/api/v1/uploads", "POST", "createUploadSession"),
        StubRoute("/api/v1/uploads/{upload_id}", "GET", "getUploadSession"),
        StubRoute("/api/v1/uploads/{upload_id}", "DELETE", "cancelUploadSession"),
        StubRoute("/api/v1/uploads/{upload_id}/content", "PATCH", "appendUploadContent"),
        StubRoute("/api/v1/uploads/{upload_id}/complete", "POST", "completeUploadSession"),
        StubRoute("/api/v1/assets", "GET", "listAssets"),
        StubRoute("/api/v1/assets/{asset_id}", "GET", "getAsset"),
        StubRoute("/api/v1/assets/{asset_id}", "PATCH", "updateAsset"),
        StubRoute("/api/v1/assets/{asset_id}/content", "GET", "downloadAssetContent"),
        StubRoute("/api/v1/assets/{asset_id}/content", "DELETE", "deleteAssetContent"),
        StubRoute("/api/v1/assets/{asset_id}/references", "GET", "listAssetReferences"),
    ),
)

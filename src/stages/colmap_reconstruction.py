import json
import subprocess
from pathlib import Path

from ..pipeline import PipelineContext, Stage


class ColmapStage(Stage):
    """Pipeline stage for COLMAP Structure-from-Motion reconstruction."""

    def __init__(
        self,
        output_dir: str = "colmap_output",
        matcher: str = "exhaustive",
        dense: bool = False,
    ):
        self.output_dir = output_dir
        self.matcher = matcher
        self.dense = dense

    def run(self, ctx: PipelineContext) -> PipelineContext:
        if not ctx.input_dir:
            ctx.errors.append("No input directory provided")
            return ctx

        image_path = Path(ctx.input_dir)
        workspace = Path(self.output_dir)
        db_path = workspace / "database.db"
        sparse_dir = workspace / "sparse"
        dense_dir = workspace / "dense"
        sparse_dir.mkdir(parents=True, exist_ok=True)

        try:
            _run(
                [
                    "colmap",
                    "feature_extractor",
                    "--database_path",
                    str(db_path),
                    "--image_path",
                    str(image_path),
                    "--ImageReader.single_camera",
                    "1",
                    "--ImageReader.camera_model",
                    "PINHOLE",
                    "--ImageReader.camera_params",
                    "512,512,512,512",
                    "--SiftExtraction.max_num_features",
                    "16384",
                ]
            )

            _run(
                [
                    "colmap",
                    f"{self.matcher}_matcher",
                    "--database_path",
                    str(db_path),
                ]
            )

            _run(
                [
                    "colmap",
                    "mapper",
                    "--database_path",
                    str(db_path),
                    "--image_path",
                    str(image_path),
                    "--output_path",
                    str(sparse_dir),
                    "--Mapper.init_min_num_inliers",
                    "10",
                    "--Mapper.min_num_matches",
                    "8",
                    "--Mapper.init_max_reg_trials",
                    "200",
                ]
            )

            sparse_model = _find_sparse_model(sparse_dir)

            gps_list = _load_gps(image_path)
            if gps_list:
                ref_path = workspace / "gps_ref.txt"
                ref_path.write_text(
                    "\n".join(f"{f} {lat} {lon} {alt}" for f, lat, lon, alt in gps_list)
                    + "\n"
                )
                _run(
                    [
                        "colmap",
                        "model_aligner",
                        "--input_path",
                        sparse_model,
                        "--output_path",
                        sparse_model,
                        "--ref_images_path",
                        str(ref_path),
                        "--ref_is_gps",
                        "1",
                        "--alignment_type",
                        "ecef",
                        "--robust_alignment",
                        "1",
                        "--robust_alignment_max_error",
                        "5.0",
                    ]
                )
                print(
                    f"COLMAP: geo-registered model using {len(gps_list)} GPS positions"
                )

            if self.dense:
                dense_dir.mkdir(exist_ok=True)
                _run(
                    [
                        "colmap",
                        "image_undistorter",
                        "--image_path",
                        str(image_path),
                        "--input_path",
                        sparse_model,
                        "--output_path",
                        str(dense_dir),
                    ]
                )
                _run(
                    ["colmap", "patch_match_stereo", "--workspace_path", str(dense_dir)]
                )
                _run(
                    [
                        "colmap",
                        "stereo_fusion",
                        "--workspace_path",
                        str(dense_dir),
                        "--output_path",
                        str(dense_dir / "fused.ply"),
                    ]
                )
                ply_path = str(dense_dir / "fused.ply")
            else:
                ply_path = str(workspace / "sparse.ply")
                _run(
                    [
                        "colmap",
                        "model_converter",
                        "--input_path",
                        sparse_model,
                        "--output_path",
                        ply_path,
                        "--output_type",
                        "PLY",
                    ]
                )

            ctx.data["point_cloud_path"] = ply_path

        except subprocess.CalledProcessError as e:
            ctx.errors.append(f"COLMAP failed at step: {e.cmd[1]}")
        except FileNotFoundError as e:
            ctx.errors.append(f"COLMAP reconstruction failed: {e}")

        return ctx


class ColmapMvsStage(Stage):
    """Run COLMAP patch-match MVS on an existing posed reconstruction."""

    def __init__(self, output_dir: str = "mvs_output"):
        self.output_dir = output_dir

    def run(self, ctx: PipelineContext) -> PipelineContext:
        sfm_model = ctx.data.get("sfm_model_path")
        if not sfm_model:
            ctx.errors.append("No sfm_model_path in context — run a SfM stage first")
            return ctx
        if not ctx.input_dir:
            ctx.errors.append("No input directory provided")
            return ctx

        image_path = Path(ctx.input_dir)
        dense_dir = Path(self.output_dir)
        dense_dir.mkdir(parents=True, exist_ok=True)
        ply_path = str(dense_dir / "fused.ply")

        try:
            _run(
                [
                    "colmap",
                    "image_undistorter",
                    "--image_path", str(image_path),
                    "--input_path", sfm_model,
                    "--output_path", str(dense_dir),
                ]
            )
            _run(["colmap", "patch_match_stereo", "--workspace_path", str(dense_dir)])
            _run(
                [
                    "colmap",
                    "stereo_fusion",
                    "--workspace_path", str(dense_dir),
                    "--output_path", ply_path,
                ]
            )
            ctx.data["point_cloud_path"] = ply_path

        except subprocess.CalledProcessError as e:
            ctx.errors.append(f"COLMAP MVS failed at step: {e.cmd[1]}")

        return ctx


def _load_gps(image_dir: Path) -> list[tuple[str, float, float, float]]:
    # Walk up to find metadata.json — may be in parent if input_dir was preprocessed
    metadata_path = None
    for candidate in [
        image_dir.parent / "metadata.json",
        image_dir.parent.parent / "metadata.json",
    ]:
        if candidate.exists():
            metadata_path = candidate
            break
    if not metadata_path:
        return []

    metadata = json.loads(metadata_path.read_text())

    # Build a stem -> GPS lookup from the original filenames
    gps_by_stem = {
        Path(img["filename"]).stem: (img["latitude"], img["longitude"], img["altitude"])
        for img in metadata["images"]
    }

    entries = []
    for img_file in sorted(image_dir.iterdir()):
        if img_file.suffix.lower() not in {".jpg", ".jpeg", ".png"}:
            continue
        stem = img_file.stem
        # Strip cube-map face suffix added by 360 conversion
        base_stem = (
            stem.removesuffix("_front")
            .removesuffix("_right")
            .removesuffix("_back")
            .removesuffix("_left")
            .removesuffix("_top")
            .removesuffix("_bottom")
        )
        coords = gps_by_stem.get(base_stem) or gps_by_stem.get(stem)
        if coords:
            entries.append((img_file.name, *coords))

    return entries


def _run(cmd: list[str]) -> None:
    step = cmd[1]
    print(f"COLMAP: running {step}...")
    subprocess.run(cmd, check=True)
    print(f"COLMAP: {step} done.")


def _find_sparse_model(sparse_dir: Path) -> str:
    models = sorted(sparse_dir.iterdir())
    if not models:
        raise FileNotFoundError(f"No sparse model found in {sparse_dir}")
    return str(models[0])

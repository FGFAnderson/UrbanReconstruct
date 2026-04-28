import subprocess
import sys
from pathlib import Path

from ..pipeline import PipelineContext, Stage


class MpSfmStage(Stage):
    """Pipeline stage for MP-SfM reconstruction."""

    def __init__(
        self,
        output_dir: str = "mpsfm_output",
        conf: str = "sp-lg_m3dv2",
        camera_params: list[float] | None = None,
        verbose: int = 1,
    ):
        self.output_dir = output_dir
        self.conf = conf
        self.camera_params = camera_params
        self.verbose = verbose

    def run(self, ctx: PipelineContext) -> PipelineContext:
        if not ctx.input_dir:
            ctx.errors.append("No input directory provided")
            return ctx

        image_path = Path(ctx.input_dir)
        workspace = Path(self.output_dir)
        workspace.mkdir(parents=True, exist_ok=True)

        reconstruct_script = Path(__file__).parent.parent / "MP-SfM" / "reconstruct.py"

        cmd = [
            sys.executable,
            str(reconstruct_script),
            "--data_dir", str(workspace),
            "--images_dir", str(image_path),
            "--conf", self.conf,
            "--verbose", str(self.verbose),
        ]

        if self.camera_params:
            intrinsics_path = workspace / "intrinsics.yaml"
            params_str = ", ".join(str(p) for p in self.camera_params)
            intrinsics_path.write_text(
                f"1:\n  params: [{params_str}]\n  images: all\n"
            )
            cmd += ["--intrinsics_pth", str(intrinsics_path)]

        try:
            subprocess.run(cmd, check=True)

            sfm_outputs = workspace / "sfm_outputs" / "rec"
            ply_path = str(workspace / "sparse.ply")

            import pycolmap
            rec = pycolmap.Reconstruction()
            rec.read(str(sfm_outputs))
            rec.extract_colors_for_all_images(str(image_path))
            rec.export_PLY(ply_path)

            ctx.data["point_cloud_path"] = ply_path
            ctx.data["sfm_model_path"] = str(sfm_outputs)

            html_path = workspace / "3d.html"
            if html_path.exists():
                ctx.data["visualization_path"] = str(html_path)

        except subprocess.CalledProcessError as e:
            ctx.errors.append(f"MP-SfM failed: {e}")

        return ctx

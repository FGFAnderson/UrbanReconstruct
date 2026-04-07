from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class PipelineContext:
    image_paths: list[Path]
    errors: list[str] = field(default_factory=list)


class Stage:
    def run(self, ctx: PipelineContext) -> PipelineContext:
        raise NotImplementedError


class Pipeline:
    def __init__(self, stages: list[Stage]):
        self.stages = stages

    def run(self, ctx: PipelineContext) -> PipelineContext:
        for stage in self.stages:
            ctx = stage.run(ctx)
            if ctx.errors:
                break
        return ctx

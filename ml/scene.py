"""Per-frame observations: the common input of the timeline, from CVAT annotations or from the models."""
from dataclasses import dataclass, field


@dataclass
class Obj:
    label: str                      # one of the CVAT labels (person, cash, safe, door, ...)
    box: list                       # [x0, y0, x1, y1] in pixels
    score: float = 1.0
    track: int | None = None
    attrs: dict = field(default_factory=dict)   # role/action for persons, state/screen/... for objects

    @property
    def center(self):
        return ((self.box[0] + self.box[2]) / 2, (self.box[1] + self.box[3]) / 2)

    @property
    def foot(self):
        return ((self.box[0] + self.box[2]) / 2, self.box[3])


@dataclass
class Frame:
    t: float                        # seconds from the start of the video
    file: str
    objs: list                      # list[Obj]

    def of(self, label):
        return [o for o in self.objs if o.label == label]


def frames_from_cvat(export_frames):
    """`load_export()` output (notebook 8.1) -> list[Frame]. Time comes from the frame file name (<vid>_<ms>.jpg)."""
    frames = []
    for f in sorted(export_frames, key=lambda f: f["frame"]):
        t = int(f["file"].rsplit("_", 1)[-1].split(".")[0]) / 1000
        objs = [Obj(b["label"], b["box"], 1.0, int(b["track_id"]) if b.get("track_id") is not None else None, b["attrs"])
                for b in f["boxes"]]
        frames.append(Frame(t, f["file"], objs))
    return frames

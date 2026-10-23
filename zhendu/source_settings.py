"""Per-source editor drafts. Invalid unfinished text survives source switches."""
from dataclasses import asdict

from .config import JobConfig, PRESET_FIELDS, TASK_FIELDS, parse_time, time_text
from .language import UserError


GROUPS = {
    "compression": PRESET_FIELDS | {"advanced"},
    "clip": {"clip", "clip_start", "clip_end"},
    "split": TASK_FIELDS,
}
DEFAULT_SYNC = {"compression": True, "clip": False, "split": False}


def draft_from_config(config):
    values = asdict(config)
    values["advanced"] = bool(config.width or config.height or config.fps or config.color_range != "source")
    values["clip_start"] = time_text(config.clip_start)
    values["clip_end"] = time_text(config.clip_end) if config.clip_end is not None else ""
    values["split_duration"] = time_text(config.split_duration)
    return values


def config_from_draft(draft):
    values = dict(draft)
    advanced = values.pop("advanced")
    if not advanced or not values["compress"]:
        values.update(width=0, height=0, fps=0.0, color_range="source")
    try:
        values["clip_start"] = parse_time(values["clip_start"]) if values["clip"] else 0.0
        values["clip_end"] = parse_time(values["clip_end"]) if values["clip"] and values["clip_end"].strip() else None
        values["split_duration"] = parse_time(values["split_duration"]) if values["split"] and values["split_mode"] == "duration" else 300.0
    except ValueError as error:
        raise UserError("时间格式无效，请使用秒数或 HH:MM:SS。", "Invalid time. Use seconds or HH:MM:SS.") from error
    return JobConfig.from_dict(values)


class SourceSettings:
    def __init__(self, defaults, sync):
        self.defaults = dict(defaults)
        self.shared = dict(defaults)
        self.sync = dict(sync)
        self.sources = {}

    def add(self, path, initial=None):
        if path not in self.sources:
            values = dict(self.defaults if initial is None else initial)
            for group, keys in GROUPS.items():
                if self.sync[group]:
                    values.update({key: self.shared[key] for key in keys})
            self.sources[path] = values

    def update(self, path, values):
        if path in self.sources:
            self.sources[path] = dict(values)
        for group, keys in GROUPS.items():
            if self.sync[group]:
                section = {key: values[key] for key in keys}
                self.shared.update(section)
                for source in self.sources.values():
                    source.update(section)

    def set_sync(self, group, enabled, values):
        self.sync[group] = enabled
        self.update(None, values)

    def get(self, path):
        return dict(self.sources[path])

    def blank(self):
        values = dict(self.defaults)
        for group, keys in GROUPS.items():
            if self.sync[group]:
                values.update({key: self.shared[key] for key in keys})
        return values

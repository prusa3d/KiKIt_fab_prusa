from __future__ import annotations

import os
import textwrap
from io import StringIO
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import schema  # type: ignore
from ruamel.yaml import YAML
from ruamel.yaml.parser import ParserError

from .project import PrusamanProject
from .text import populateText


class Choice:
    def __init__(self, allowed: List[Any]) -> None:
        self.allowed: List[Any] = allowed

    def validate(self, data: Any) -> Any:
        if data in self.allowed:
            return data
        raise schema.SchemaError(f"'{data}' is not one of allowed: {', '.join(self.allowed)}")

class Filepath:
    def __init__(self, exists: Optional[bool]=False, extension: Optional[str]=None,
                 base: Union[str, Path]=None):
        self.exists = exists
        self.extension = extension
        self.base = base

    def validate(self, data: Any) -> str:
        if not isinstance(data, str):
            raise schema.SchemaError(f"Path is not string; got {data}")
        if self.base is not None:
            data = os.path.join(self.base, data)
        if self.extension is not None and not data.endswith(self.extension):
            raise schema.SchemaError(f"The file doesn't have extension {self.extension}")
        if self.exists and not os.path.exists(data):
            raise schema.SchemaError(f"'{data} doesn't exists")
        return data


class PrusamanConfiguration:
    def __init__(self, configuration: Dict[str, Any], base: Union[str, Path]) -> None:
        self.cfg: Dict[str, Any] = configuration
        try:
            self._buildSchema(base).validate(self.cfg)
        except schema.SchemaError as e:
            raise RuntimeError(str(e)) from None

    @classmethod
    def fromFile(cls, path: Union[str, Path]) -> PrusamanConfiguration:
        try:
            yaml = YAML(typ='safe')
            with open(path, "r") as f:
                content = f.read()
            # Expand variables used in the configuration
            content = populateText(content)
            cfg = yaml.load(StringIO(content))
            return cls(cfg, os.path.dirname(path))
        except FileNotFoundError:
            raise FileNotFoundError(
                f"Configuration file {path} doesn't exist.") from None
        except ParserError as e:
            parserMessage = str(e)
            parserMessage = parserMessage.replace(str(path), Path(path).name)
            raise RuntimeError(
                f"Invalid syntax of source file {path}:\n{textwrap.indent(parserMessage, '    ')}") from None

    @classmethod
    def fromProject(cls, project: PrusamanProject) -> PrusamanConfiguration:
        return PrusamanConfiguration.fromFile(project.getConfiguration())

    def __getitem__(self, key: Any) -> Any:
        if isinstance(key, str):
            if key in self.cfg:
                return self.cfg[key]
        raise NotImplementedError("This is bug: Getting arbitrary objects is not supported")

    @staticmethod
    def _buildSchema(base: Union[str, Path]) -> schema.Schema:
        from schema import And, Or, Schema
        manualPanel = {
            "type": "manual",
            "source": Filepath(exists=True, extension=".kicad_pcb", base=base)
        }
        scriptPanel = {
            "type": "script",
            "script": "script"
        }
        kikitPanel = {
            "type": "kikit",
            "configuration": Filepath(exists=True, extension=".json", base=base)
        }
        panelSchema = And(
            {
                "type": Choice(["manual", "script", "kikit"]),
                str: object
            },
            Or(manualPanel, scriptPanel, kikitPanel))

        return Schema({
            "revision": And(int, lambda x: x > 0),
            "board_id": Or(str, int),
            "bom_filter": Or("kibom", "legacy", "pnb"),
            "panel": panelSchema
        })

from typing import Optional
import click
import sys
import textwrap
from . import __version__
from .manugenerator import Manugenerator, PrusamanProject, replaceDirectory, stdioPrompt
from tempfile import TemporaryDirectory
from pathlib import Path

class StdReporter:
    def __init__(self, reportWarnings: bool, reportInfo: bool,
                 defaultAnswer: Optional[bool]) -> None:
        self._repW = reportWarnings
        self._repI = reportInfo
        self._defAnswer = defaultAnswer
        self.triggered = False

    def warning(self, tag: str, message: str) -> None:
        if not self._repW or len(message) == 0:
            return
        self.triggered = True
        self._print("Warning", tag, message)

    def info(self, tag: str, message: str) -> None:
        if not self._repI or len(message) == 0:
            return
        self._print("Info", tag, message)

    def prompt(self, tag: str, prompt: str) -> None:
        if self._defAnswer is not None:
            return self._defAnswer
        return stdioPrompt(tag, prompt)

    def _print(self, header: str, tag: str, message: str) -> None:
        BODY = 80
        wMessages = textwrap.wrap(message, BODY)
        head, *tail = wMessages
        sys.stderr.write(f"{header + ' ' + tag + ': ':>20}{head}\n")
        if len(tail) > 0:
            sys.stderr.write(textwrap.indent("\n".join(tail), 20 * " ") + "\n")


@click.command()
@click.argument("source", type=click.Path(file_okay=True, dir_okay=True, exists=True))
@click.argument("outputdir", type=click.Path(file_okay=False, dir_okay=True))
@click.option("--force", "-f", is_flag=True,
    help="If existing path already contains files, overwrite them.")
@click.option("--silent", "-s", is_flag=True,
    help="Report only errors")
@click.option("--werror", "-w", is_flag=True,
    help="Treat warnings as errors")
@click.option("--question", default="ask",
              type=click.Choice(["yes", "no", "ask"], case_sensitive=False),
    help="Decide how to handle interactive prompt")
def make(source, outputdir, force, werror, silent, question):
    """
    Make manufacturing files for a project (SOURCE) into OUTPUTDIR.
    """
    from .pcbnew_common import fakeKiCADGui

    app = fakeKiCADGui()

    try:
        project = PrusamanProject(source)

        if Path(outputdir).exists() and not force:
            raise RuntimeError(f"Cannot produce output: {outputdir} already exists.\n" +
                                "If you wish to rewrite the files, rerun the command with --force")

        defaultAnswer = None
        if question == "yes":
            defaultAnswer = True
        if question == "no":
            defaultAnswer = False

        reporter = StdReporter(
            reportWarnings=(werror or not silent),
            reportInfo=(not silent),
            defaultAnswer=defaultAnswer)

        # We use temporary directory so we do not damage any existing files in
        # process. Once we are done, we atomically swap the directories
        with TemporaryDirectory(prefix="prusaman_") as tmpdir:
            generator = Manugenerator(project, tmpdir,
                            reportInfo=reporter.info,
                            reportWarning=reporter.warning,
                            askContinuation=reporter.prompt)
            generator.make()

            if werror and reporter.triggered:
                raise RuntimeError("Warnings were treated as errors. See warnings above.")

            Path(outputdir).mkdir(parents=True, exist_ok=True)
            replaceDirectory(outputdir, tmpdir)
    except Exception as e:
        sys.stderr.write(f"Error occurred: \n{textwrap.indent(str(e), '   ')}\n")
        sys.stderr.write("\nNo output files produced\n")


@click.command()
@click.argument("source", type=click.Path(file_okay=True, dir_okay=True, exists=True))
@click.argument("outputdir", type=click.Path(file_okay=False, dir_okay=True))
def bump():
    """
    Bump project (SOURCE) version and place the new version into OUTPUTDIR
    """
    raise NotImplementedError("This functionality is not implemented yet.")


@click.group()
@click.version_option(__version__)
def cli():
    """
    Prusaman: Generate PCB manufacturing data
    """
    pass

cli.add_command(make)
cli.add_command(bump)

if __name__ == "__main__":
    cli()


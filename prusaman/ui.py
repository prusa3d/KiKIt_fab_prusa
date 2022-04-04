import click
from . import __version__
from .manugenerator import Manugenerator, PrusamanProject, replaceDirectory
from tempfile import TemporaryDirectory
from pathlib import Path

@click.command()
@click.argument("source", type=click.Path(file_okay=True, dir_okay=True, exists=True))
@click.argument("outputdir", type=click.Path(file_okay=False, dir_okay=True))
@click.option("--force", "-f", is_flag=True,
    help="If existing path already contains files, overwrite them.")
@click.option("--silent", "-s", is_flag=True,
    help="Report only errors")
@click.option("--werror", "-w", is_flag=True,
    help="Treat warnings as errors")
def make(source, outputdir, force, werror, silent):
    """
    Make manufacturing files for a project (SOURCE) into OUTPUTDIR.
    """
    project = PrusamanProject(source)

    # We use temporary directory so we do not damage any existing files in
    # process. Once we are done, we atomically swap the directories
    with TemporaryDirectory(prefix="prusaman_") as tmpdir:
        generator = Manugenerator(project, tmpdir)
        generator.make()

        Path(outputdir).mkdir(parents=True, exist_ok=True)
        replaceDirectory(outputdir, tmpdir)


@click.command()
@click.argument("source", type=click.Path(file_okay=True, dir_okay=True, exists=True))
@click.argument("outputdir", type=click.Path(file_okay=False, dir_okay=True))
def bump():
    """
    Bump project (SOURCE) version and place the new version into OUTPUTDIR
    """
    pass


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


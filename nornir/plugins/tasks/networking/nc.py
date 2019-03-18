from typing import Any, Dict, List, Optional
from enum import Enum
import json
import difflib

from nornir.core.task import Result, Task

class NcDatastore(str, Enum):
    running = "running",
    candidate = "candidate",
    startup = "startup"


def get_config(
    task: Task,
    source: NcDatastore,
    path: str,
    exclude: List[str] = None,
    depth: int = 99
) -> Result:
    """
    Get configuration from specified datastore `source` on router

    Arguments:
        source: datastore to use (type: `NcDatastore`), e.g. `NcDatastore.candidate`
        path: path to intended element (e.g.: `/router/interface`)
            last element of path mqy be an '=' expression, e.g. `/router/interface/interface-name=to_sr2`
        depth: level depth of nested objects. A value of 0 means all is returned

    Examples:

        Simple example::

            > nr.run(task=nc_get_config,
            >        source=NcDatastore.running,
            >        path=["router", "interface"])

    Returns:
        Result object with the following attributes set:
          * result (``dict``): dictionary with the result of the getter
    """
    conn = task.host.get_connection("ncclient", task.nornir.config)
    result = conn.get_config(getattr(source, 'name'), path=path, depth=depth, exclude=exclude)
    return Result(host=task.host, result=result)

def get(
    task: Task,
    path: List[str],
    depth: int = 99,
    exclude: List[str] = None
) -> Result:
    """
    Get state information from specified resource ('path') on router

    Arguments:
        path: list of elements from root to intended element. 
         (e.g.: `['router', 'interface']`)
        depth: level depth of nested objects. A value of 0 means all is returned

    Examples:

        Simple example::

            > nr.run(task=nc_get_config,
            >        path=["router", "interface"])

    Returns:
        Result object with the following attributes set:
          * result (``dict``): dictionary with the result of the getter
    """
    conn = task.host.get_connection("ncclient", task.nornir.config)
    result = conn.get(path=path, depth=depth, exclude=exclude)
    return Result(host=task.host, result=result)


def nc_validate(
    task: Task,
    source: Any,
    destination: Any,
    path: str,
) -> Result:

    conn = task.host.get_connection("ncclient", task.nornir.config)
    if isinstance(source, NcDatastore):
        source_dict = conn.get_config(getattr(source, 'name'), path=path)
    elif isinstance(source, dict):
        source_dict = source
    else:
        raise ValueError("parameter 'source' has invalid type")
    if isinstance(destination, NcDatastore):
        dest_dict = conn.get_config(getattr(destination, 'name'), path=path)
    elif isinstance(destination, dict):
        dest_dict = destination
    else:
        raise ValueError("parameter 'destination' has invalid type")
 
    source_json = json.dumps(source_dict, indent=2)
    dest_json = json.dumps(dest_dict, indent=2)

    result = ""
    for line in difflib.unified_diff(
            source_json.splitlines(keepends=True),
            dest_json.splitlines(keepends=True),
            fromfile=source, tofile=destination
    ):
        result += line
    return Result(host=task.host, result=result)

def nc_configure(
    task: Task,
    dry_run: Optional[bool] = None,
    configuration: Optional[str] = None,
    path: Optional[str] = None,
#    replace: bool = False
) -> Result:
    """
    Loads configuration into network device using netconf
    
    Arguments:
        dry_run: only show what would change rather than modifying config
        configuration: config to load
        replace: replace or merge(default) configuration
        
    Returns:
        Result object with following attributes set:
            * changed (``bool``): task has changed config or not
            * diff (``str``): changes to device config
    """
    conn = task.host.get_connection("ncclient", task.nornir.config)
    conn.edit_config(config=configuration,target="candidate", path=path)
    diff = conn.compare_config()

    dry_run = task.is_dry_run(dry_run)
    if not dry_run and diff:
        conn.commit_config()
    else:
        conn.discard_config()
    return Result(host=task.host, diff=diff, changed=len(diff) > 0)


def close(
    task: Task
) -> None:
    task.host.close_connection("ncclient")

    

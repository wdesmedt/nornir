import os
from copy import deepcopy

from nornir.core.task import Result, Task

import ruamel.yaml


def load_intent(
        task: Task, 
        directory :str
    ) -> Result:
    """
    Loads intents from intent files
    
    Arguments:

    Examples:

    """
    global_intent = {}
    group_intent = {}
    host_intent = {}

    for dirpath, _, files in os.walk(directory):
        for name in files:
            with open(os.path.join(dirpath, name), "r") as f:
                yml = ruamel.yaml.YAML(typ="safe")
                data = yml.load(f)
            if "_path" in data:
                path = data["_path"]
                data = { path: data}
                target_scope = data[path].get('_target_scope', None)
                if target_scope.upper() == "GLOBAL":
                    _merge(global_intent, data)
                elif target_scope.upper() == "GROUP":
                    target_groups = data[path].get('_target_groups', [])
                    for group in target_groups:
                        if task.host.has_parent_group(group):
                            _merge(group_intent, data)
                elif target_scope.upper() == "HOST":
                    if data[path].get('_target_host', None) == task.host.name:
                        _merge(host_intent, data)                       

    _merge(group_intent, global_intent)
    _merge(host_intent, group_intent)

    for path, resource in host_intent.items():        
        m_keys = [k for k in resource.keys() if k.startswith("_target")]
        for k in m_keys:
            del resource[k]

    return Result(host=task.host, result=host_intent)


def _merge(a, b):
    for key in b:
        if key in a:
            if isinstance(a[key], dict) and isinstance(b[key], dict):
                _merge(a[key], b[key])
            else:
                pass # a always wins
        else:
            a[key] = b[key]

                    

def load_yaml(task: Task, file: str) -> Result:
    """
    Loads a yaml file.

    Arguments:
        file: path to the file containing the yaml file to load

    Examples:

        Simple example with ``ordered_dict``::

            > nr.run(task=load_yaml,
                     file="mydata.yaml")

    Returns:
        Result object with the following attributes set:
          * result (``dict``): dictionary with the contents of the file
    """
    with open(file, "r") as f:
        yml = ruamel.yaml.YAML(typ="safe")
        data = yml.load(f)

    return Result(host=task.host, result=data)

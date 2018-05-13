from brigade.core.task import Result

import napalm_yang


def _napalm_yang_common(task, models, root, mode, profile, device, native):
    if isinstance(profile, str):
        profile = [profile]
    if isinstance(models, str):
        models = [models]

    if not root:
        root = napalm_yang.base.Root()

    for model in models:
        if isinstance(model, str):
            model = getattr(napalm_yang.models, model)
        root.add_model(model)

    if mode == "config":
        root.parse_config(device=device, profile=profile, native=native)
    elif mode == "state":
        root.parse_state(device=device, profile=profile, native=native)
    else:
        raise ValueError(
            "I don't know which mode is '{}'. Supported: config, state".format(mode)
        )

    return Result(host=task.host, result=root)


def napalm_yang_load_from_device(task, models, root=None, mode="config", profile=None):
    """
    Example:

        result = task.run(
            task=napalm_yang_load_from_device,
            models=["openconfig_interfaces", "openconfig_network_instance"],
        )
    """
    device = task.host.get_connection("napalm")
    return _napalm_yang_common(task, models, root, mode, profile, device, None)


def napalm_yang_load_from_files(
    task, models, filenames, root=None, mode="config", profile=None
):
    """
    Example:

        result = task.run(
            task=napalm_yang_load_from_files,
            filenames=f"{task.host}/backup.config",
            models=["openconfig_interfaces", "openconfig_network_instance"],
            profile="eos",
        )
    """
    profile = profile or task.host.nos

    if isinstance(filenames, str):
        filenames = [filenames]

    native = []
    for filename in filenames:
        with open(filename, "r") as f:
            native.append(f.read())

    return _napalm_yang_common(task, models, root, mode, profile, None, native)


def napalm_yang_load_from_native(
    task, models, native, root=None, mode="config", profile=None
):
    """
    Example:

        with open(f"{task.host}/backup.config", "r") as f:
            native = f.read()

        result = task.run(
            task=napalm_yang_load_from_native,
            native=native,
            models=["openconfig_interfaces", "openconfig_network_instance"],
            profile="eos",
        )
    """
    profile = profile or task.host.nos

    if isinstance(native, str):
        native = [native]

    return _napalm_yang_common(task, models, root, mode, profile, None, native)


def napalm_yang_load_from_dict(task, data, root=None):
    """
    Example:

        data = {
            "interfaces": {
                "interface": {
                    "et1": {
                        "name": "et1",
                        "config": {"description": "a description", "mtu": 9000},
                    },
                    "et2": {
                        "name": "et2",
                        "config": {"description": "another description", "mtu": 1500},
                    },
                }
            }
        }
        result = task.run(
            task=napalm_yang_load_from_dict,
            data=data
        )
    """
    if not root:
        root = napalm_yang.base.Root()
    root.load_dict(data)
    return Result(host=task.host, result=root)

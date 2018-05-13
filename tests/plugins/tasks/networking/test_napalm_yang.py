import os

from brigade.plugins.tasks import connections, networking

#  from napalm_yang import helpers
#  helpers.config_logging()


THIS_DIR = os.path.dirname(os.path.realpath(__file__)) + "/mocked/napalm_yang"


class Test(object):

    def test_napalm_yang_load_from_device_config(self, brigade):
        opt = {"path": THIS_DIR}
        d = brigade.filter(name="dev3.group_2")
        d.run(connections.napalm_connection, optional_args=opt)

        result = d.run(
            task=networking.napalm_yang_load_from_device,
            models=["openconfig_interfaces", "openconfig_network_instance"],
            profile="eos",
        )

        assert result
        processed = False
        for h, r in result.items():
            processed = True
            assert "Port-Channel1" in r.result.interfaces.interface
            assert "bgp bgp" in r.result.network_instances.network_instance[
                "global"
            ].protocols.protocol
        assert processed

    def test_napalm_yang_load_from_device_state(self, brigade):
        opt = {"path": THIS_DIR}
        d = brigade.filter(name="dev3.group_2")
        d.run(connections.napalm_connection, optional_args=opt)

        result = d.run(
            task=networking.napalm_yang_load_from_device,
            models="openconfig_interfaces",
            profile="eos",
            mode="state",
        )

        assert result
        processed = False
        for h, r in result.items():
            processed = True
            assert "Port-Channel1" in r.result.interfaces.interface
        assert processed

    def test_napalm_yang_load_from_files(self, brigade):
        d = brigade.filter(name="dev3.group_2")
        result = d.run(
            task=networking.napalm_yang_load_from_files,
            filenames="{}/cli.1.show_running_config_all.0".format(THIS_DIR),
            models=["openconfig_interfaces", "openconfig_network_instance"],
            profile="eos",
        )

        assert result
        processed = False
        for h, r in result.items():
            processed = True
            assert "Port-Channel1" in r.result.interfaces.interface
            assert "bgp bgp" in r.result.network_instances.network_instance[
                "global"
            ].protocols.protocol
        assert processed

    def test_napalm_yang_load_from_native(self, brigade):
        with open("{}/cli.1.show_running_config_all.0".format(THIS_DIR), "r") as f:
            native = f.read()

        d = brigade.filter(name="dev3.group_2")
        result = d.run(
            task=networking.napalm_yang_load_from_native,
            native=native,
            models=["openconfig_interfaces", "openconfig_network_instance"],
            profile="eos",
        )

        assert result
        processed = False
        for h, r in result.items():
            processed = True
            assert "Port-Channel1" in r.result.interfaces.interface
            assert "bgp bgp" in r.result.network_instances.network_instance[
                "global"
            ].protocols.protocol
        assert processed

    def test_napalm_yang_load_from_dict(self, brigade):
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

        d = brigade.filter(name="dev3.group_2")
        result = d.run(task=networking.napalm_yang_load_from_dict, data=data)

        assert result
        processed = False
        for h, r in result.items():
            processed = True
            assert r.result.to_dict() == data
        assert processed

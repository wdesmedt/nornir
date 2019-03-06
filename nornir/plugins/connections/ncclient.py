import json
from typing import Any, Dict, List, Optional

from ncclient import manager
import xmltodict

from nornir.core.configuration import Config
from nornir.core.connections import ConnectionPlugin


class Ncclient(ConnectionPlugin):
    """
    This plugin connects to the device using ncclient and sets the
    relevant connection.

    Inventory:
        extras: passed as it is to the napalm driver
    """

    def open(
        self,
        hostname: Optional[str],
        username: Optional[str],
        password: Optional[str],
        port: Optional[int],
        platform: Optional[str],
        extras: Optional[Dict[str, Any]] = None,
        configuration: Optional[Config] = None,
    ) -> None:
        extras = extras or {}

        parameters: Dict[str, Any] = {
            "host": hostname,
            "username": username,
            "password": password,
            "hostkey_verify": False,
        }

        _connection = manager.connect(**parameters)
        self.connection = self
        self._connection = _connection
        self.state = {
            'connected': _connection.connected,
            'session_id': _connection.session_id,
            'timeout': _connection.timeout,
        }


    def close(self) -> None:
        self._connection.close_session()

    def get_config(
        self,
        source: str = "running",
        path: List[str] = [],
        strip: bool = True
    
    ):
        if len(path) > 0:
            filter_str = self._expand_filter(path)
        else:
            filter_str = ""
        nc_filter = f'<filter><configure xmlns="urn:nokia.com:sros:ns:yang:sr:conf">{filter_str}</configure></filter>'
        reply = self._connection.get_config(source, filter = nc_filter)
        if strip:
            d = {}
            try:
                d = xmltodict.parse(reply.xml)['rpc-reply']['data'].get('configure', {})
            except AttributeError:
                pass
            try:
                del d['@xmlns']
            except KeyError:
                pass
        else:
            d = xmltodict.parse(reply.xml)['rpc-reply']['data']
        return d
        

    def get(
        self,
        path: List[str] = [],
        strip: bool = True
    
    ):
        if len(path) > 0:
            filter_str = self._expand_filter(path)
        else:
            filter_str = ""
        nc_filter = f'<filter><state xmlns="urn:nokia.com:sros:ns:yang:sr:state">{filter_str}</state></filter>'
        reply = self._connection.get(filter = nc_filter)
        if strip:
            d = {}
            try:
                d = xmltodict.parse(reply.xml)['rpc-reply']['data'].get('state', {})
            except AttributeError:
                pass
            try:
                del d['@xmlns']
            except KeyError:
                pass
        else:
            d = xmltodict.parse(reply.xml)['rpc-reply']['data']
        return d

    def edit_config(
        self,
        config: Dict[str, Any],
        target: str = "candidate",
        default_operation: str = "merge",
    ) -> None:
        try:
            xml_str = xmltodict.unparse(config)
        except ValueError as e:
            raise(f'Cannot convert dict {config} to xml: {e}')
        xml_str = '<config><configure xmlns="urn:nokia.com:sros:ns:yang:sr:conf">' + xml_str + '</configure></config>'
        self._connection.edit_config(xml_str, target=target, default_operation=default_operation)


    def commit(self):
        self._connection.commit()

    def discard(self):
        self._connection.discard_changes()

    @staticmethod
    def _expand_filter(filter: List[str]) -> str:
        f = filter.copy()
        expanded_filter = ""
        while len(f):
            e = f.pop()
            expanded_filter = f"<{e}>{expanded_filter}</{e}>"
        return expanded_filter

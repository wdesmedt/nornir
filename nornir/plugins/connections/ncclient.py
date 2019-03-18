import json
import difflib
from copy import deepcopy
from collections import OrderedDict
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
        path: str = None,
        depth: int = None,
        exclude: List[str] = None, 
        strip: bool = True
    
    ):
        if path:
            path = path.strip('/').split('/')
        else:
            path = []
        
        if len(path) > 0:
            filter_str = self._expand_filter(path)
        else:
            filter_str = ""
        nc_filter = f'<filter><configure xmlns="urn:nokia.com:sros:ns:yang:sr:conf">{filter_str}</configure></filter>'
        reply = self._connection.get_config(source, filter = nc_filter)
        if strip:
            d = OrderedDict()
            try:
                d = xmltodict.parse(reply.xml)['rpc-reply']['data'].get('configure', {})
            except AttributeError:
                pass
            try:
                del d['@xmlns']
            except KeyError:
                pass
            for node in path:
                if '=' in node:
                    break
                try:
                    d = d[node]
                except KeyError:
                    raise("Node in supplied path not in result")
            if len(path) > 0:
                d = OrderedDict([(path[-1], d)])    # this is needed to get rid of potential attribs in root of elem
                                                    # that would still be there if just doing d = d[node[-1]]

        else:
            d = xmltodict.parse(reply.xml)['rpc-reply']['data']
        if depth or exclude:
            d = reduce_dict(d, depth=depth, exclude=exclude)
        return d
        

    def get(
        self,
        path: str = None,
        depth: int = None,
        exclude: List[str] = None,
        strip: bool = True
    
    ):
        if path:
            path = path.strip('/').split('/')
        else:
            path = []

        if len(path) > 0:
            filter_str = self._expand_filter(path)
        else:
            filter_str = ""
        nc_filter = f'<filter><state xmlns="urn:nokia.com:sros:ns:yang:sr:state">{filter_str}</state></filter>'
        reply = self._connection.get(filter = nc_filter)
        if strip:
            d = OrderedDict()
            try:
                d = xmltodict.parse(reply.xml)['rpc-reply']['data'].get('state', {})
            except AttributeError:
                pass
            try:
                del d['@xmlns']
            except KeyError:
                pass
            for node in path:
                if isinstance(d, list):
                    if '=' not in node:
                        raise ValueError(f"key=value node in path required for list of elements")
                    found = False
                    k, v = node.split('=')
                    for elem in d:
                        if elem[k] == v:
                            d = elem
                            found = True
                            break
                    if not found:
                        raise ValueError(f"{k}={v} not found in list")
                else:
                    try:
                        d = d[node]
                    except KeyError:
                        raise("Node in supplied path not in result")
            if len(path) > 0:
                d = OrderedDict([(path[-1], d)])
        
        else:
            d = xmltodict.parse(reply.xml)['rpc-reply']['data']
        if depth or exclude:
            d = reduce_dict(d, depth=depth, exclude=exclude)
        return d

    def edit_config(
        self,
        config: Dict[str, Any],
        target: str = "candidate",
        default_operation: str = "merge",
        path: str = ""
    ) -> None:

        path = path.strip('/').split('/')
        expanded_config = deepcopy(config)
        for el in reversed(path):
            if '=' in el:
                k, v = el.split('=')
                expanded_config[k] = v
            else:
                expanded_config = {el: expanded_config }
        try:
            xml_str = xmltodict.unparse(expanded_config, full_document=False)
        except ValueError as e:
            raise ValueError(f'Cannot convert dict {expanded_config} to xml: {e}')
        xml_str = '<config><configure xmlns="urn:nokia.com:sros:ns:yang:sr:conf">' + xml_str + '</configure></config>'
        self._connection.edit_config(xml_str, target=target, default_operation=default_operation)

    def compare_config(self):
        """
        Compares 'running' and 'candidate' datastores on router
        Requires netconf user to have access to console in addition to netconf
            to query full running config (/admin display-config)
        """
        
        source_dict = self.get_config(source="running")
        dest_dict = self.get_config('candidate')

        source_json = json.dumps(source_dict, indent=2)
        dest_json = json.dumps(dest_dict, indent=2)

        diff = ""
        for line in difflib.unified_diff(
            source_json.splitlines(keepends=True),
            dest_json.splitlines(keepends=True),
            fromfile="running", tofile="candidate"
        ):
            diff += line
        return diff


    def commit_config(self):
        self._connection.commit()


    def discard_config(self):
        self._connection.discard_changes()


    @staticmethod
    def _expand_filter(filter: List[str]) -> str:
        f = filter.copy()
        expanded_filter = ""
        while len(f):
            e = f.pop()
            if '=' in e:
                if len(expanded_filter) > 0:
                    raise ValueError(f"match expr can only be in last elem of path")
                k, v = e.split('=')
                expanded_filter = f"<{k}>{v}</{k}>"
            else:
                expanded_filter = f"<{e}>{expanded_filter}</{e}>"
        return expanded_filter

def reduce_dict(
    d: OrderedDict,
    depth:int, 
    exclude:List[str]
    ) -> Dict[str, Any]:

    if isinstance(d, OrderedDict):
        result = OrderedDict()
    else:
        result = dict()
    for k, v in d.items():
        if exclude and k in exclude:
            continue
        if isinstance(v, list):
            if len(v) > 0 and isinstance(v[0], dict):
                depth -= 1
                if depth > 0:
                    new_list = []
                    for e in v:
                        r_dict = reduce_dict(e, depth=depth, exclude=exclude)
                        if len(r_dict.keys()) > 0:
                            new_list.append(reduce_dict(e, depth=depth, exclude=exclude))
                    if len(new_list) > 0:
                        result[k] = new_list
                else:
                    break
        
        else:
            if isinstance(v, dict):
                depth -= 1
                if depth > 0:
                    v = reduce_dict(v, depth=depth, exclude=exclude)
                else:
                    break
            result[k] = v

    return result
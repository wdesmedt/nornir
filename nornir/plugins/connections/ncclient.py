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
        strip: bool = True,
        path_sep: str = "/"
    
    ):
        return self._get_data(
            data_type="configuration",
            source=source,
            path=path,
            depth=depth,
            exclude=exclude,
            strip=strip,
            path_sep=path_sep
        )
        

    def get(
        self,
        path: str = None,
        depth: int = None,
        exclude: List[str] = None,
        strip: bool = True,
        path_sep: str = "/"
    ):
        return self._get_data(
            data_type="state",
            path=path,
            depth=depth,
            exclude=exclude,
            strip=strip,
            path_sep=path_sep
        )


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


    def _get_data(
        self,
        data_type: str = "configuration",
        source: str = None,
        path: str = None,
        depth: int = None,
        exclude: List[str] = None, 
        strip: bool = True,
        path_sep: str = "/"
    
    ):
        if data_type not in ['configuration', 'state']:
            raise ValueError(f"Invalid data_type param: {data_type}")
        if path:
            path = path.strip(path_sep).split(path_sep)
        else:
            path = []
        
        if len(path) > 0:
            filter_str = self._expand_filter(path)
        else:
            filter_str = ""
        if data_type == "configuration":
            nc_filter = f'''<filter><configure xmlns="urn:nokia.com:sros:ns:yang:sr:conf">
               {filter_str}
                </configure></filter>'''
            reply = self._connection.get_config(source, filter = nc_filter)
        else: 
            nc_filter = f'''<filter><state xmlns="urn:nokia.com:sros:ns:yang:sr:state">
                {filter_str}
                </state></filter>'''
            reply = self._connection.get(filter = nc_filter)

        if strip:
            d = OrderedDict()
            d = xmltodict.parse(reply.xml)['rpc-reply']['data']
            if not d:
                return {}
            if data_type == "configuration":
                d = d.get('configure', {})
            else:
                d = d.get('state', {})
            del d['@xmlns']
            for node in path:
                if '=' in node:
                    continue
                if isinstance(d, list):
                    break
                d = d.get(node)
                if not d:
                    return {}
        else:
            d = xmltodict.parse(reply.xml)['rpc-reply']['data']

        if isinstance(d, list):
            d_temp = OrderedDict()
            d_temp['_count'] = len(d) 
            for n, elem in enumerate(d):
                d_temp[n] = elem
            d = d_temp
        if depth or exclude:
            d = reduce_dict(d, depth=depth, exclude=exclude)
        return d


    @staticmethod
    def _expand_filter(filter: List[str]) -> str:
        f = filter.copy()
        expanded_filter = ""
        while len(f):
            e = f.pop()
            if '=' in e:
                k, v = e.split('=')
                expanded_filter += f"<{k}>{v}</{k}>"
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
#!/usr/bin/python3

import os
import json
import redis
import requests
import configparser

misp_module_url = 'http://localhost:6666'

default_config_path = os.path.join(os.environ['AIL_HOME'], 'configs', 'misp_modules.cfg')

sys.path.append(os.path.join(os.environ['AIL_BIN'], 'lib/'))
import ConfigLoader

config_loader = ConfigLoader.ConfigLoader()
r_serv = config_loader.get_redis_conn("ARDB_DB")
config_loader = None

def init_config(config_path=default_config_path):
    config = configparser.ConfigParser()
    if os.path.isfile(config_path):
        config.read(config_path)
    else:
        config.add_section('misp_modules')
        config.set('misp_modules', 'url', 'http://localhost')
        config.set('misp_modules', 'port', '6666')
    return config

def init_module_config(module_json, config, config_path=default_config_path):
    if 'config' in module_json['meta'] and module_json['meta']['config']:
        if module_json['name'] not in config:
            config.add_section(module_json['name'])
        for config_var in module_json['meta']['config']:
            if config_var not in config[module_json['name']]:
                config.set(module_json['name'], config_var, '')
    return config

def load_modules_list():
    req = requests.get(f'{misp_module_url}/modules')
    if req.status_code == 200:
        all_misp_modules = req.json()
        all_modules = [
            module_json
            for module_json in all_misp_modules
            if 'hover' in module_json['meta']['module-type']
            or 'expansion' in module_json['meta']['module-type']
        ]

        config = init_config()
        r_serv.delete('misp_modules')
        for module_json in all_modules:
            config = init_module_config(module_json, config, config_path=default_config_path)
            r_serv.hset('misp_modules', module_json['name'], json.dumps(module_json))

        with open(default_config_path, 'w') as f:
            config.write(f)

    else:
        print('Error: Module service not reachable.')


def build_config_json(module_name):
    misp_module_config = configparser.ConfigParser()
    misp_module_config.read(default_config_path)
    dict_config = {}
    if module_name in misp_module_config:
        for config_key in misp_module_config[module_name]:
            if config_value := misp_module_config[module_name][config_key]:
                dict_config[config_key] = config_value
    return dict_config

def build_enrichment_request_json(module_name, var_name, var_value):
    # # TODO: add error handler
    request_dict = {'module': module_name, var_name: var_value}
    if config_json := build_config_json(module_name):
        request_dict['config'] = config_json
    return json.dumps(request_dict)

def misp_module_enrichment_request(misp_module_url, misp_module_port, request_content):
    # # TODO: check if module is enabled
    endpoint_url = f'{misp_module_url}:{misp_module_port}/query'
    req = requests.post(endpoint_url, headers={'Content-Type': 'application/json'}, data=request_content)
    if req.status_code == 200:
        if response := req.json():
            return parse_module_enrichment_response(response)
    else:
        print(f'error: {req.status_code} Enrichment service not reachable.')
        return ''

def parse_module_enrichment_response(misp_module_response):
    print(misp_module_response)
    response_values = []
    if 'results' in misp_module_response:
        # # TODO: handle misp_format (Attribute, Object, Tags)
        response_types = []
        for result in misp_module_response['results']:
            # get all types
            response_types.extend(iter(result['types']))
            # get all values
            response_values.extend(iter(result['values']))
            # TODO: handle / verify / use response types
            #print(response_types)
    return response_values

if __name__ == "__main__":

    load_modules_list()

    misp_module_url = 'http://localhost'
    misp_module_port = 6666

    bitcoin_address = 'bitcoin_address'
    test_content = build_enrichment_request_json('btc_steroids', 'btc', bitcoin_address)
    print(test_content)
    misp_module_enrichment_request(misp_module_url, misp_module_port, test_content)

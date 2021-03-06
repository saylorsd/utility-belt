import os
import re
import csv
from collections import OrderedDict
from json import loads, dumps
import operator
import requests
import time

def execute_query(URL,query=None):
    # [ ] If the query might result in a response that is too large or
    # too burdensome for the CKAN instance to generate, paginate
    # this process somehow.

    # Information about better ways to handle requests exceptions:
    #http://stackoverflow.com/questions/16511337/correct-way-to-try-except-using-python-requests-module/16511493#16511493
    payload = {}
    if query is not None:
        payload = {'sql': query}
    try:
        r = requests.get(URL, payload)
    except requests.exceptions.Timeout:
        # Maybe set up for a retry, or continue in a retry loop
        r = requests.get(URL, payload)
    except requests.exceptions.TooManyRedirects:
        # Tell the user their URL was bad and try a different one
        print("This URL keeps redirecting. Maybe you should edit it.")
    except requests.exceptions.RequestException as e:
        # catastrophic error. bail.
        print(e)
        sys.exit(1)
    return r

def pull_and_verify_data(URL, site, failures=0):
    success = False
    try:
        r = execute_query(URL)
        result = r.json()["result"]
        records = result["records"]
        # You can just iterate through using the _links results in the
        # API response:
        #    "_links": {
        #  "start": "/api/action/datastore_search?limit=5&resource_id=5bbe6c55-bce6-4edb-9d04-68edeb6bf7b1",
        #  "next": "/api/action/datastore_search?offset=5&limit=5&resource_id=5bbe6c55-bce6-4edb-9d04-68edeb6bf7b1"
        list_of_fields_dicts = result['fields']
        all_fields = [d['id'] for d in list_of_fields_dicts]
        if r.status_code != 200:
            failures += 1
        else:
            URL = site + result["_links"]["next"]
            success = True
    except:
        records = None
        all_fields = None
        #raise ValueError("Unable to obtain data from CKAN instance.")
    # Information about better ways to handle requests exceptions:
    #http://stackoverflow.com/questions/16511337/correct-way-to-try-except-using-python-requests-module/16511493#16511493

    return records, all_fields, URL, success

def get_fields(site,resource_id):
    success = False
    all_fields = None
    URL = "{}/api/action/datastore_search?resource_id={}&limit=0".format(site, resource_id)
    try:
        r = execute_query(URL)
        list_of_fields_dicts = r.json()['result']['fields']
        all_fields = [d['id'] for d in list_of_fields_dicts]
        success = True
    except:
        success = False

    return all_fields, success

def get_resource(site,resource_id,chunk_size=500):
    limit = chunk_size
    URL_template = "{}/api/3/action/datastore_search?resource_id={}&limit={}"

    URL = URL_template.format(site, resource_id, limit)

    all_records = []

    failures = 0
    records = [None, None, "Boojum"]
    k = 0
    while len(records) > 0 and failures < 5:
        time.sleep(2)
        records, fields, next_URL, success = pull_and_verify_data(URL,site,failures)
        if success:
            if records is not None:
                all_records += records
            URL = next_URL
            failures = 0
        else:
            failures += 1
        k += 1
        print("{} iterations, {} failures, {} records, {} total records".format(k,failures,len(records),len(all_records)))

    return all_records, fields, success


def retrieve_new_data(self):
    URL = "{}/api/3/action/datastore_search_sql".format(self.site)

    #query = "SELECT {} FROM \"{}\" WHERE \"{}\" > '{}';".format(self.field, self.resource_id, self.index_field, self.last_index_checked)
    query = "SELECT \"{}\",\"{}\" FROM \"{}\" WHERE \"{}\" > {};".format(self.field, self.index_field, self.resource_id, self.index_field, int(self.last_index_checked)-1)
    #query = "SELECT {} FROM \"{}\";".format(self.field, self.resource_id)

    print(query)

    r = execute_query(URL,query)

    print(r.status_code)
    if r.status_code != 200:
        r = requests.get(URL, {'sql': query})
    if r.status_code == 200:
        records = json.loads(r.text)["result"]["records"]
        last_index_checked = records[-1][self.index_field]
        return records, last_index_checked, datetime.now()
    else:
        raise ValueError("Unable to obtain data from CKAN instance.")
        # Information about better ways to handle requests exceptions:
        #http://stackoverflow.com/questions/16511337/correct-way-to-try-except-using-python-requests-module/16511493#16511493


def to_dict(input_ordered_dict):
    return loads(dumps(input_ordered_dict))

def value_or_blank(key,d,subfields=[]):
    if key in d:
        if d[key] is None:
            return ''
        elif len(subfields) == 0:
            return d[key]
        else:
            return value_or_blank(subfields[0],d[key],subfields[1:])
    else:
        return ''

def write_or_append_to_csv(filename,list_of_dicts,keys):
    if not os.path.isfile(filename):
        with open(filename, 'wb') as g:
            g.write(','.join(keys)+'\n')
    with open(filename, 'ab') as output_file:
        dict_writer = csv.DictWriter(output_file, keys, extrasaction='ignore', lineterminator='\n')
        #dict_writer.writeheader()
        dict_writer.writerows(list_of_dicts)


def write_to_csv(filename,list_of_dicts,keys):
    with open(filename, 'wb') as output_file:
        dict_writer = csv.DictWriter(output_file, keys, extrasaction='ignore', lineterminator='\n')
        dict_writer.writeheader()
        dict_writer.writerows(list_of_dicts)

def unique_values(xs,field):
    return { x[field] if field in x else None for x in to_dict(xs) }

def char_delimit(xs,ch):
    return(ch.join(xs))

def sort_dict(d):
    return sorted(d.items(), key=operator.itemgetter(1))

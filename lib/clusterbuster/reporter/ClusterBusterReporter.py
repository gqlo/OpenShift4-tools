#!/usr/bin/env python3

# Copyright 2022 Robert Krawitz/Red Hat
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json
import re
import sys
import textwrap
from copy import deepcopy
import io
import os
import base64
import importlib
import inspect
from .metrics.PrometheusMetrics import PrometheusMetrics


class ClusterBusterReporter:
    """
    Report generator for ClusterBuster
    """

    @staticmethod
    def report_one(jdata: dict, format: str, **kwargs):
        if format == 'none' or format is None:
            return
        if format == 'raw':
            json.dump(jdata, sys.stdout, indent=2)
            return
        if 'workload_reporting_class' in jdata['metadata']:
            workload = jdata["metadata"]["workload_reporting_class"]
        else:
            workload = jdata["metadata"]["workload"]
        if 'runtime_class' not in jdata['metadata']:
            runtime_class = jdata['metadata']['options']['runtime_classes'].get('default')
            if runtime_class:
                jdata['metadata']['runtime_class'] = runtime_class
        try:
            imported_lib = importlib.import_module(f'..{workload}_reporter', __name__)
        except Exception as exc:
            print(f'Warning: no handler for workload {workload}, issuing generic summary report ({exc})', outfile=sys.stderr)
            return ClusterBusterReporter(jdata, format).create_report()
        try:
            for i in inspect.getmembers(imported_lib):
                if i[0] == f'{workload}_reporter':
                    return i[1](jdata, format).create_report(**kwargs)
        except Exception as exc:
            raise(exc)

    @staticmethod
    def validate_dir(dirname: str):
        if dirname.find('.FAIL') >= 0 or dirname.find('.tmp') >= 0:
            return False
        if not re.search('(^|/)(cpusoaker|fio|uperf|files)-(kata|runc)-[0-9]+[^/]*$', dirname):
            return False
        return os.path.isfile(os.path.join(dirname, "clusterbuster-report.json"))

    @staticmethod
    def enumerate_dirs(items: list):
        answers = list()
        for item in items:
            if isinstance(item, str):
                if os.path.isfile(item):
                    answers.append(item)
                elif os.path.isdir(item):
                    if os.path.isfile(os.path.join(item, "clusterbuster-report.json")):
                        answers.append(os.path.join(item, "clusterbuster-report.json"))
                    else:
                        subitems = sorted(os.listdir(item))
                        for subitem in subitems:
                            subitem = os.path.join(item, subitem)
                            if ClusterBusterReporter.validate_dir(subitem):
                                answers.append(os.path.join(subitem, "clusterbuster-report.json"))
        return answers

    @staticmethod
    def report(items, format: str, **kwargs):
        answers = list()
        if not items:
            items = [None]
        elif not isinstance(items, list):
            items = [items]
        for item in ClusterBusterReporter.enumerate_dirs(items):
            with open(item) as f:
                answers.append(ClusterBusterReporter.report_one(json.load(f), format, **kwargs))
        for item in items:
            jdata = dict()
            if isinstance(item, str):
                continue
            if isinstance(item, io.TextIOBase):
                jdata = json.load(item)
            elif item is None:
                jdata = json.load(sys.stdin)
            elif isinstance(item, dict):
                jdata = item
            else:
                raise Exception(f"Unrecognized item {item}")
            answers.append(ClusterBusterReporter.report_one(jdata, format, **kwargs))
        return answers

    @staticmethod
    def print_report(items, format: str, outfile=sys.stdout, **kwargs):
        answers = ClusterBusterReporter.report(items, format, **kwargs)
        if format.startswith('json'):
            json.dump(answers, outfile, indent=2)
        elif format != "none":
            print("\n\n".join(answers))

    @staticmethod
    def list_report_formats():
        return ['none', 'summary', 'verbose', 'raw',
                'json-summary', 'json', 'json-verbose',
                'parseable-summary', 'parseable-verbose']

    def __init__(self, jdata: dict, report_format: str, indent: int = 2, report_width=78):
        """
        Initializer for generic ClusterBuster report
        :param jdata: JSON data to report
        :param report_format: Report format, one of json-summary, json, json-verbose, verbose, summary
        :param indent: Per-level indentation
        :param report_width: Width of the report
        """
        self._jdata = deepcopy(jdata)
        self._format = report_format
        self._all_clients_are_on_the_same_node = self.__are_clients_all_on_same_node()
        self._summary = {'cpu_time': 0,
                         'runtime': 0,
                         'total_instances': 0}
        self._rows = []
        self._timeline_vars = []
        self._accumulator_vars = []
        self._summary_indent = indent
        self._report_width = report_width
        self._verbose_indent = 0
        self._header_keys = {}
        self._fields_to_copy = []
        self._expect_row_data = True
        self._add_explicit_timeline_vars(['data_start_time', 'data_end_time', 'pod_start_time', 'pod_create_time'])
        self._add_accumulators(['user_cpu_time', 'system_cpu_time', 'cpu_time', 'data_elapsed_time',
                                'timing_parameters.sync_rtt_delta'])

    def create_report(self):
        """
        Create a report
        """
        if 'Results' in self._jdata and 'worker_results' in self._jdata['Results']:
            rows = self._jdata['Results']['worker_results']
        else:
            rows = []
        for row in rows:
            self._create_row(row)

        if len(rows) > 0:
            self._add_summary()

        if self._format.startswith('json'):
            return self.__create_json_report()
        else:
            return self.__create_text_report()

    def _generate_summary(self, results: dict):
        """
        Generate summary results.  If a subclass wishes to override this to generate
        its own data, it must call this explicitly prior to generating its own results.

        :param results: Summary results that are updated
        """
        results['Total Clients'] = self._summary['total_instances']
        if 'elapsed_time_average' in self._summary:
            results['Elapsed time average'] = self._prettyprint(self._summary['elapsed_time_average'],
                                                                precision=3, suffix='sec')
            results['Pod creation interval'] = self._prettyprint(self._summary['pod_create_interval'],
                                                                 precision=3, suffix='sec')
            self._summary['pod_creation_rate'] = self._safe_div(self._summary['total_instances'],
                                                                (self._summary['last_pod_create_time'] -
                                                                 self._summary['first_pod_create_time']), number_only=True)
            results['Pod creation rate'] = self._prettyprint(self._safe_div(self._summary['total_instances'],
                                                                            (self._summary['last_pod_create_time'] -
                                                                             self._summary['first_pod_create_time'])),
                                                             precision=3, suffix='pods/sec', base=0)
            results['User CPU time'] = self._prettyprint(self._summary['user_cpu_time'],
                                                         precision=3, suffix='sec')
            results['System CPU seconds'] = self._prettyprint(self._summary['system_cpu_time'],
                                                              precision=3, suffix='sec')
            results['CPU seconds'] = self._prettyprint(self._summary['cpu_time'],
                                                       precision=3, suffix='sec')
            self._summary['cpu_utilization'] = self._safe_div(self._summary['cpu_time'], self._summary['data_run_interval'])
            results['CPU utilization'] = self._prettyprint(self._summary['cpu_utilization'], precision=3, base=100, suffix='%')
            if 'metrics' in self._summary:
                results['Metrics'] = {}
                for key, value in self._summary['metrics'].items():
                    results['Metrics'][key] = value
            results['First pod start'] = self._prettyprint(self._summary['first_pod_start_time'],
                                                           precision=3, suffix='sec')
            results['Last pod start'] = self._prettyprint(self._summary['last_pod_start_time'],
                                                          precision=3, suffix='sec')
            results['Pod start interval'] = self._prettyprint(self._summary['pod_start_interval'],
                                                              precision=3, suffix='sec')
            self._summary['pod_start_rate'] = self._safe_div(self._summary['total_instances'],
                                                             (self._summary['last_pod_start_time'] -
                                                              self._summary['first_pod_start_time']), number_only=True)
            results['Pod start rate'] = self._prettyprint(self._safe_div(self._summary['total_instances'],
                                                                         (self._summary['last_pod_start_time'] -
                                                                          self._summary['first_pod_start_time'])),
                                                          precision=3, suffix='pods/sec', base=0)
            results['First run start'] = self._prettyprint(self._summary['first_data_start_time'],
                                                           precision=3, suffix='sec')
            results['Last run start'] = self._prettyprint(self._summary['last_data_start_time'],
                                                          precision=3, suffix='sec')
            results['Run start interval'] = self._prettyprint(self._summary['data_start_interval'],
                                                              precision=3, suffix='sec')
            self._summary['absolute_sync_error'] = (self._summary['data_start_interval'] +
                                                    self._summary['data_end_interval']) / 2
            results['Absolute sync error'] = self._prettyprint((self._summary['data_start_interval'] +
                                                                self._summary['data_end_interval']) / 2,
                                                               precision=3, suffix='sec')
            self._summary['relative_sync_error'] = self._summary['overlap_error']
            results['Relative sync error'] = self._prettyprint(self._summary['overlap_error'],
                                                               precision=4, base=100, suffix='%')
            results['Sync max RTT delta'] = self._prettyprint(self._summary['timing_parameters']['max_sync_rtt_delta'],
                                                              precision=3, suffix='sec')
            results['Sync avg RTT delta'] = self._prettyprint(self._summary['timing_parameters']['avg_sync_rtt_delta'],
                                                              precision=3, suffix='sec')
            results['First run end'] = self._prettyprint(self._summary['first_data_end_time'],
                                                         precision=3, suffix='sec')
            results['Last run end'] = self._prettyprint(self._summary['last_data_end_time'],
                                                        precision=3, suffix='sec')
            results['Net elapsed time'] = self._prettyprint(self._summary['data_run_interval'],
                                                            precision=3, suffix='sec')
            timing = self._jdata['Results']['controller_timing']
            results['Sync offset from host'] = self._prettyprint(timing['sync_ts'] - timing['second_controller_ts'],
                                                                 precision=3, suffix='sec')
            offset_error = timing['second_controller_ts'] - timing['first_controller_ts']
            results['Possible controller-sync offset error'] = self._prettyprint(offset_error,
                                                                                 precision=3, suffix='sec')

    def _generate_row(self, results, row: dict):
        """
        Generate row results.  If a subclass wishes to override this to generate
        its own summary, it must call this explicitly prior to generating its own results.

        :param results: Output row results that are updated
        :param row: Input row
        """
        pass

    def _create_row(self, row: dict):
        """
        Create one output row.  If a subclass wishes to override this for its own
        custom processing, it should call this explicitly prior to generating
        its own results.

        :param row: Input row
        :return: Index of row in self._rows.  This is returned to allow subclasses
                 to determine what to update.

        """
        rowhash = {}
        self._summary['total_instances'] += 1
        if 'namespace' in row:
            rowhash['namespace'] = row['namespace']
            rowhash['pod'] = row['pod']
            rowhash['container'] = row['container']
            rowhash['node'] = self.__find_node_for_pod(namespace=row['namespace'], pod=row['pod'])
            rowhash['process_id'] = row['process_id']
            for var in self._timeline_vars:
                self.__update_timeline_val(var, row, self._summary)
            for accumulator in self._accumulator_vars:
                self.__update_accumulator_val(accumulator, row, self._summary, rowhash)
            for field_to_copy in self._fields_to_copy:
                self.__copy_field(field_to_copy, row, self._summary, rowhash)

        self._rows.append(rowhash)
        return len(self._rows)-1

    def __format_memory_value(self, number):
        return self._prettyprint(number, precision=3, suffix='B', integer=1)

    def __format_byte_rate_value(self, number):
        return self._prettyprint(number, precision=3, base=1000, suffix='B/sec')

    def __format_pkt_rate_value(self, number):
        return self._prettyprint(number, precision=3, base=1000, suffix='pkts/sec')

    def __format_cpu_value(self, number):
        return self._prettyprint(number, precision=3, base=100, suffix='%')

    def _add_summary(self):
        """
        Add summary information that can only be computed at the end.
        This is mostly for timeline variables and metrics
        """
        if 'data_elapsed_time' in self._summary:
            self._summary['elapsed_time_average'] = self._safe_div(self._summary['data_elapsed_time'],
                                                                   self._summary['total_instances'])
            self._summary['pod_create_interval'] = self._summary['last_pod_create_time'] - self._summary['first_pod_create_time']
            self._summary['data_run_interval'] = self._summary['last_data_end_time'] - self._summary['first_data_start_time']
            self._summary['pod_start_interval'] = self._summary['last_pod_start_time'] - self._summary['first_pod_start_time']
            self._summary['data_start_interval'] = self._summary['last_data_start_time'] - self._summary['first_data_start_time']
            self._summary['data_end_interval'] = self._summary['last_data_end_time'] - self._summary['first_data_end_time']
            self._summary['overlap_error'] = self._safe_div(((self._summary['data_start_interval'] +
                                                              self._summary['data_end_interval']) / 2),
                                                            self._summary['elapsed_time_average'])
        if 'metrics' in self._jdata:
            metrics = PrometheusMetrics(self._jdata['metrics'])
            self._summary['metrics'] = {}
            mtr = self._summary['metrics']
            mtr['Maximum memory working set'] = metrics.get_max_value_by_key('containerMemoryWorkingSet-clusterbuster',
                                                                             printfunc=self.__format_memory_value)
            mtr['Receive bytes/sec'] = metrics.get_max_value_by_key('rxNetworkBytes-WorkerByNode',
                                                                    printfunc=self.__format_byte_rate_value)
            mtr['Transmit bytes/sec'] = metrics.get_max_value_by_key('txNetworkBytes-WorkerByNode',
                                                                     printfunc=self.__format_byte_rate_value)
            mtr['Receive packets/sec'] = metrics.get_max_value_by_key('rxNetworkPackets-WorkerByNode',
                                                                      printfunc=self.__format_pkt_rate_value)
            mtr['Transmit packets/sec'] = metrics.get_max_value_by_key('txNetworkPackets-WorkerByNode',
                                                                       printfunc=self.__format_pkt_rate_value)
            mtr['CPU utilization'] = {
                'User': metrics.get_max_value_by_key('nodeCPUUser-Workers',
                                                     printfunc=self.__format_cpu_value),
                'System': metrics.get_max_value_by_key('nodeCPUSys-Workers',
                                                       printfunc=self.__format_cpu_value),
                'Total': metrics.get_max_value_by_key('nodeCPUUtil-Workers',
                                                      printfunc=self.__format_cpu_value),
                'Total Workers': metrics.get_max_value_by_key('containerCPU-clusterbuster',
                                                              printfunc=self.__format_cpu_value)
                }

    def _add_explicit_timeline_vars(self, vars_to_update: list):
        """
        Add report variables of type timeline (e. g. absolute start
        and end times).  These are combined to determine absolute
        start and finish of various operations, and compute synchronization
        errors, for summarization

        first_<var> and last_<var> names are synthesized in the summary.

        Variables may be dotted components, in which case they are extracted
        from the JSON structure.

        Variables in this list that are not present in the output are ignored.

        :param vars_to_update: List of variables to add
        """
        self._timeline_vars.extend(vars_to_update)

    def _add_timeline_vars(self, vars_to_update: list):
        """
        Add report variables of type timeline (e. g. absolute start
        and end times).  These are combined to determine absolute
        start and finish of various operations, and compute synchronization
        errors, for summarization

        first_<var>, last_<var>, and <var>_elapsed_time names are synthesized
        in the summary.

        Variables may be dotted components, in which case they are extracted
        from the JSON structure.

        Variables in this list that are not present in the output are ignored.

        :param vars_to_update: List of variables to add
        """
        for var in vars_to_update:
            self._timeline_vars.append(f'{var}_start')
            self._timeline_vars.append(f'{var}_end')
            self._fields_to_copy.append(f'{var}_elapsed_time')

    def _add_accumulators(self, accumulators: list):
        """
        Add report variables that are accumulated, with max, min,
        square, and counter variables synthesized.  These are used in
        the summary and copied into rows.

        Variables may be dotted components, in which case they are extracted
        from the JSON structure.

        Variables in this list that are not present in the output are ignored.

        :param vars_to_update: List of variables to add
        """
        self._accumulator_vars.extend(accumulators)

    def _add_fields_to_copy(self, fields_to_copy: list):
        """
        Add report variables that are copied into result rows.

        Variables may be dotted components, in which case they are extracted
        from the JSON structure.

        Variables in this list that are not present in the output are ignored.

        :param vars_to_update: List of variables to add
        """
        self._fields_to_copy = fields_to_copy

    def _set_header_components(self, headers: list):
        """
        Set the list of header names that are used in the detail
        report, by level.

        :param headers: List of header names by depth.
        """
        self._header_keys['Detail'] = headers

    def _set_summary_header_components(self, headers: list):
        """
        Set the list of header names that are used in the summary
        report, by level.

        :param headers: List of header names by depth.
        """
        self._header_keys['Summary'] = headers

    def _fformat(self, num: float, precision: float = 5):
        """
        Return a formatted version of a float.  If precision is 0, no decimal point is printed.
        :param num:
        :param precision:
        """
        try:
            if precision > 1:
                return f'{num:.{precision}f}'
            else:
                return int(round(num))
        except Exception:
            return num

    def _prettyprint(self, num: float, precision: float = 5, integer: int = 0, base: int = 1024, suffix: str = ''):
        """
        Return a pretty printed version of a float.
        Base 100:  print percent
        Base 1000: print with decimal units (1000, 1000000...)
        Base 1024: print with binary units (1024, 1048576...)
                   This only applies to values larger than 1;
                   smaller values are always printed with
                   decimal units
        Base 0:    do not use any units
        Base -1:   Only print units for <1
        :param num:
        :param precision:
        :param base: 0, 1000, 1024, or -1
        :param integer: print as integer
        :param suffix: trailing suffix (e. g. "B/sec")
        """
        if num is None:
            return 'None'
        try:
            num = float(num)
        except Exception:
            return str(num)
        if self._format.startswith('json'):
            return num
        elif 'parseable' in self._format:
            if integer != 0 or num == 0:
                return str(int(num))
            else:
                if base == 100:
                    precision += 2
                elif abs(float(num)) < .000001:
                    precision += 9
                elif abs(float(num)) < .001:
                    precision += 6
                elif abs(float(num)) < 1:
                    precision += 3
                return self._fformat(num, precision=precision)
        elif base == 0:
            if suffix and suffix != '':
                return f'{self._fformat(num, precision=precision)} {suffix}'
            else:
                return f'{self._fformat(num, precision=precision)}'
        elif base == 100:
            return f'{self._fformat(num * 100, precision=precision)} %'
        elif base == 1000 or base == 10:
            infix = ''
            base = 1000
        elif base == 1024 or base == 2:
            infix = 'i'
            base = 1024
        elif base != -10 or base != -1 or base != -1000:
            raise(Exception(f'Illegal base {base} for prettyprint; must be 1000 or 1024'))
        if base > 0 and abs(num) >= base ** 5:
            return f'{self._fformat(num / (base ** 5), precision=precision)} P{infix}{suffix}'
        elif base > 0 and abs(num) >= base ** 4:
            return f'{self._fformat(num / (base ** 4), precision=precision)} T{infix}{suffix}'
        elif base > 0 and abs(num) >= base ** 3:
            return f'{self._fformat(num / (base ** 3), precision=precision)} G{infix}{suffix}'
        elif base > 0 and abs(num) >= base ** 2:
            return f'{self._fformat(num / (base ** 2), precision=precision)} M{infix}{suffix}'
        elif base > 0 and abs(num) >= base ** 1:
            return f'{self._fformat(num / base, precision=precision)} K{infix}{suffix}'
        elif abs(num) >= 1 or num == 0:
            if integer != 0 or num == 0:
                precision = 0
            return f'{self._fformat(num, precision=precision)} {suffix}'
        elif abs(num) >= 10 ** -3:
            return f'{self._fformat(num * (1000), precision=precision)} m{suffix}'
        elif abs(num) >= 10 ** -6:
            return f'{self._fformat(num * (1000 ** 2), precision=precision)} u{suffix}'
        elif abs(num) >= 10 ** -9:
            return f'{self._fformat(num * (1000 ** 3), precision=precision)} n{suffix}'
        else:
            return f'{self._fformat(num * (1000 ** 4), precision=precision)} p{suffix}'

    def _safe_div(self, num: float, denom: float, precision: int = None, as_string: bool = False,
                  number_only: bool = False):
        """
        Safely divide two numbers.  Return 'N/A' if denominator is zero.
        :param num: Numerator
        :param denom: Denominator
        :param precision: Precision to round the result
        :param as_string: If true, return value as string
        :param number_only: If true, only return a number (0 for N/A)
        """
        try:
            result = float(num) / float(denom)
            if precision is None:
                return result
            elif precision == 0:
                return int(round(result, 0))
            elif as_string:
                return self._fformat(result, precision)
            else:
                return round(result, precision)
        except Exception:
            if number_only:
                return 0
            else:
                return 'N/A'

    def _wrap_text(self, text: str):
        """
        Wrap and indent text appropriately for reporting.
        This should not be used for multi-line strings.
        :param text: String to wrap
        :return: Filled string
        """
        if 'parseable' in self._format:
            return text
        else:
            return textwrap.fill(text, width=self._report_width, subsequent_indent='  ',
                                 break_long_words=False, break_on_hyphens=False)

    def _insert_into(self, results: dict, path: list, value):
        """
        Insert value into results at location specified by path,
        creating missing keys as needed.
        :param results: Dictionary into which value should be inserted
        :param path: Path within directory where data should be inserted
        :param value: What should be inserted
        """

        results1 = results
        while len(path) > 1:
            key = path.pop(0)
            if key not in results1:
                results1[key] = {}
            results1 = results1[key]
        results1[key] = value

    def _copy_formatted_value(self, var: str, dest: dict, source: dict):
        """
        Copy a value from source to dest, with optional formatting of the form
        var[:key1=val1:key2=val2...]
        :param var: path to copy
        :param dest: where to copy it to
        :param source: where to copy it from
        """
        optstrings = var.split(':')
        rvar = optstrings.pop(0)
        if len(optstrings) > 0:
            args = {}
            for option in optstrings:
                try:
                    name, value = option.split('=', 1)
                    try:
                        value = int(value)
                    except Exception:
                        pass
                    args[name] = value
                except Exception as exc:
                    raise Exception(f"Cannot parse option {option}: {exc}")
            dest[rvar] = self._prettyprint(source[rvar], **args)
        else:
            dest[var] = source[var]

    def __are_clients_all_on_same_node(self):
        """
        Determine whether all clients ran on the same node.  This is used to determine
        whether items sensitive to exact time of day should be reported; if they are on
        different nodes whose times may be out of synchronization, these items should
        not be reported.
        :return:
        """
        node = None
        for obj in self._jdata['api_objects']:
            if obj['kind'] == 'Pod' and 'clusterbuster-client' in obj['metadata']['labels'] and obj['metadata']['labels']['clusterbuster-client']:
                if not node:
                    node = obj['spec']['nodeName']
                elif obj['spec']['nodeName'] != node:
                    return False
        return True

    def __find_node_for_pod(self, namespace: str, pod: str):
        """
        Find the node on which the pod under examination ran by searching JSON data.
        :param namespace: Namespace of the pod.
        :param pod: Name of the pod.
        :return:
        """
        for obj in self._jdata['api_objects']:
            if obj['kind'] == 'Pod' and obj['metadata']['namespace'] == namespace and obj['metadata']['name'] == pod:
                return obj['spec']['nodeName']
        return None

    def __row_name(self, row: dict):
        """
        Synthesize a row name for purpose of sorting.

        :param row:
        :return: Row name suitable for sorting.
        """
        if 'namespace' in row:
            return f'{row["namespace"]}~{row["pod"]}~{row["container"]}~{row.get("process_id", 0):#07d}'
        else:
            return ''

    def __copy_field(self, var: str, row, summary, rowhash: dict):
        """
        Copy one field from an input row to an output row.  This recurses for deep copy.
        :param var: Name of variable to copy
        :param row: Input row from JSON
        :param rowhash: Output row
        """
        components = var.split('.', 1)
        if len(components) > 1:
            if components[0] not in row:
                return
            if (isinstance(row[components[0]], list)):
                for element in row[components[0]]:
                    self.__copy_field(components[1], element, summary, rowhash)
            else:
                if components[0] not in rowhash:
                    rowhash[components[0]] = {}
                if components[0] not in summary:
                    summary[components[0]] = {}
                self.__copy_field(components[1], row[components[0]], summary[components[0]], rowhash[components[0]])

        if len(components) > 1:
            if components[0] not in rowhash:
                [components[0]] = {}
            if components[0] not in summary:
                summary[components[0]] = {}
            self.__copy_field(components[1], row[components[0]], summary[components[0]], rowhash[components[0]])
        else:
            self._copy_formatted_value(var, rowhash, row)
            self._copy_formatted_value(var, summary, row)

    def __update_timeline_val(self, var: str, row, summary: dict):
        """
        Update one summary timeline value.  This recurses for deep copy.
        :param var: Name of variable to update
        :param row: Input row from JSON
        :param summary: Summary of report
        """
        components = var.split('.', 1)
        if len(components) > 1:
            if components[0] not in row:
                return
            if (isinstance(row[components[0]], list)):
                for element in row[components[0]]:
                    self.__update_timeline_val(components[1], element, summary)
            else:
                if components[0] not in summary:
                    summary[components[0]] = {}
                self.__update_timeline_val(components[1], row[components[0]], summary[components[0]])
        else:
            row_val = row[f'{var}']
            mvar = None
            m = re.search(r'(.*)_(start|end)$', var)
            if m:
                mvar = f'{m.group(1)}'
                tvar = f'{mvar}_elapsed_time'
                svar = f'{mvar}_start'
                evar = f'{mvar}_end'
            if f'first_{var}' not in summary or row_val < summary[f'first_{var}']:
                summary[f'first_{var}'] = row_val
                if var.endswith('_start'):
                    summary[var] = row_val
            if f'last_{var}' not in summary or row_val > summary[f'last_{var}']:
                summary[f'last_{var}'] = row_val
                if var.endswith('_end'):
                    summary[var] = row_val
            if mvar and f'last_{evar}' in summary and f'first_{svar}' in summary:
                summary[tvar] = summary[f'last_{evar}'] - summary[f'first_{svar}']

    def __normalize_timeline_val(self, var: str, summary: dict, offset: float):
        """
        Normalize a timeline variable to the initial offset between host and pod
        :param var: Name of variable to update
        :param summary: Summary of report
        :param offset: Starting time offset
        """
        components = var.split('.', 1)
        if len(components) > 1:
            self.__normalize_timeline_val(components[1], summary[components[0]], offset)
        else:
            summary[f'first_{var}'] -= offset
            summary[f'last_{var}'] -= offset

    def __update_accumulator_val(self, var: str, row, summary, rowhash: dict):
        """
        Update one accumulator value.  This recurses for deep copy.
        :param var: Name of variable to update
        :param row: Input row from JSON
        :param rowhash: Output row
        :param summary: Summary of report
        """
        components = var.split('.', 1)
        if len(components) > 1:
            if components[0] not in row:
                return
            if (isinstance(row[components[0]], list)):
                for element in row[components[0]]:
                    self.__update_accumulator_val(components[1], element, summary, rowhash)
            else:
                if components[0] not in summary:
                    summary[components[0]] = {}
                if components[0] not in rowhash:
                    rowhash[components[0]] = {}
                self.__update_accumulator_val(components[1], row[components[0]], summary[components[0]], rowhash[components[0]])
        else:
            if var not in row:
                return
            row_val = row[var]
            if var not in summary:
                summary[var] = 0
            var_counter = f'{var}_counter'
            var_sq = f'{var}_sq'
            var_stdev = f'stdev_{var}'
            var_max = f'max_{var}'
            var_min = f'min_{var}'
            var_avg = f'avg_{var}'
            if var_counter not in summary:
                summary[var_counter] = 0
                summary[var_max] = row_val
                summary[var_min] = row_val
                summary[var_avg] = row_val
                summary[var_sq] = 0
            summary[var] += row_val
            summary[var_counter] += 1
            summary[var_sq] += row_val * row_val
            if (row_val > summary[var_max]):
                summary[var_max] = row_val
            if (row_val < summary[var_min]):
                summary[var_min] = row_val
            summary[var_avg] = summary[var] / summary[var_counter]
            if summary[var_counter] >= 2:
                # From https://www.strchr.com/standard_deviation_in_one_pass
                summary[var_stdev] = ((summary[var_sq] / summary[var_counter]) - (summary[var_avg] ** 2)) ** 0.5
            else:
                summary[var_stdev] = 0
            rowhash[var] = row_val

    def __strip_suffix(self, num):
        n = str(num).strip()
        try:
            idx = n.index(' ')
            return n[:idx]
        except Exception:
            return num

    def __isnum(self, num):
        num = self.__strip_suffix(num)
        try:
            _ = float(num)
            return True
        except Exception:
            return False

    def __compute_report_width(self, results: dict, indentation: int = None):
        """
        Compute recursively column widths for keys (taking into account indentation)
        and the integer part of floats.

        :param results: Results to be scanned
        :param indentation: Desired per-level indentation (default per the class)
        :return width: (maximum) width for the key field
        :return integer_width: (maximum) width for the integer component of any numbers
                               Strings are treated as having zero integer width,
                               but this value is used to determine string indentation
                               so that if possible strings are right aligned with
                               integers
        """
        width = 0
        integer_width = 0
        if indentation is None:
            indentation = self._summary_indent
        for key in results:
            if isinstance(results[key], dict):
                fwidth, nwidth = self.__compute_report_width(results[key], indentation=indentation)
                fwidth += indentation
            else:
                try:
                    nwidth = len(str(int(float(self.__strip_suffix(results[key])))))
                except Exception:
                    nwidth = 0
                fwidth = len(key.strip())
            if fwidth > width:
                width = fwidth
            if nwidth > integer_width:
                integer_width = nwidth
        return [width, integer_width]

    def __parseable_path(self, path: list):
        answer = '.'.join([elt.replace(':', '') for elt in path]).lower().replace('\n', '')
        for char in [' ', ',', '/', '"', "'"]:
            answer = answer.replace(char, '_')
        while '__' in answer:
            answer = answer.replace('__', '_')
        return '.'.join([self._jdata['metadata']['job_name'], answer])

    def __indent(self, string: str, target_column: int):
        if 'parseable' in self._format:
            return string
        else:
            return textwrap.indent(string, prefix=' ' * (target_column + 2))[target_column+2:]

    def __print_subreport(self, path: list, results: dict, headers: list, key_column=0, value_column=0,
                          depth_indentation=None, integer_width=0, outfile=sys.stdout):
        """
        Print a sub-report recursively

        :param results: Results to be printed
        :param headers: List of headers to be used for nested components
        :param key_column: Left column for printing of keys (incremented recursively)
        :param value_column: Left column for printing of values
        :param depth_indentation: Per-level indentation
        :param integer_width: (maximum) width for the integer component of any numbers
                               Strings are treated as having zero integer width,
                               but this value is used to determine string indentation
                               so that if possible strings are right aligned with
                               integers
        """

        header_keys = []
        value_keys = []
        if depth_indentation is None:
            depth_indentation = self._summary_indent
        for key in results.keys():
            if key in results:
                if isinstance(results[key], dict):
                    header_keys.append(key)
                else:
                    value_keys.append(key)

        header_name = None
        if key_column > 0 and len(headers):
            headers = deepcopy(headers)
            header_name = headers.pop(0)
        for key in results.keys():
            if 'parseable' not in self._format and key.startswith('\n'):
                print('', file=outfile)
            npath = path + [key]
            if isinstance(results[key], dict):
                if 'parseable' not in self._format:
                    if header_name:
                        print(f'{" " * key_column}{header_name}: {key.strip()}:', file=outfile)
                    else:
                        print(f'{" " * key_column}{key.strip()}:', file=outfile)
                self.__print_subreport(npath, results[key], headers,
                                       key_column=key_column + depth_indentation,
                                       value_column=value_column,
                                       depth_indentation=depth_indentation,
                                       integer_width=integer_width, outfile=outfile)
            else:
                value = results[key]
                if 'parseable' in self._format:
                    if '\n' in str(value):
                        value = base64.b64encode(value.encode('ascii')).decode()
                    else:
                        value = str(value).strip()
                    print(f'{self.__parseable_path(npath)}: {value}', file=outfile)
                else:
                    try:
                        nwidth = len(str(int(float(self.__strip_suffix(value)))))
                    except Exception:
                        value = str(value).strip()
                        if len(value) > integer_width:
                            nwidth = None
                        else:
                            nwidth = len(value)
                    if nwidth is None:
                        integer_indent = 0
                    else:
                        integer_indent = integer_width - nwidth
                    value = str(value)
                    if "\n" in value:
                        value = textwrap.indent(value, prefix=' ' * (key_column + 2))
                        print(f'{" " * key_column}{key.strip()}:\n{value}', file=outfile)
                    else:
                        indentation = " " * (value_column + integer_indent - key_column - len(key.strip()))
                        print(f'{" " * key_column}{key.strip()}: {indentation}{value}',
                              file=outfile)
            if 'parseable' not in self._format and key.endswith('\n'):
                print('', file=outfile)

    def __print_report(self, results: dict, outfile, value_column=0, integer_width=0):
        """
        Print report.  Headers are used by key.
        Key names that start with a newline have a newline printed before each instance.
        Key names that end with a newline have a newline printed after the data in each instance.

        :param results: Results to be printed
        :param value_column: Left column for printing of values
        :param integer_width: (maximum) width for the integer component of any numbers
                               Strings are treated as having zero integer width,
                               but this value is used to determine string indentation
                               so that if possible strings are right aligned with
                               integers
        """
        for key in results.keys():
            headers = []
            if key in self._header_keys:
                headers = self._header_keys[key]
            if len(results[key].keys()):
                if 'parseable' not in self._format:
                    print(f'{key}:', file=outfile)
                self.__print_subreport([key], results[key], headers=headers,
                                       key_column=self._summary_indent, value_column=value_column,
                                       depth_indentation=self._summary_indent,
                                       integer_width=integer_width, outfile=outfile)

    def __create_json_report(self):
        """
        Create JSON format report
        """
        results = {}
        if 'verbose' in self._format and len(self._rows):
            results['Detail'] = {}
            self._rows.sort(key=self.__row_name)
            for row in self._rows:
                self._generate_row(results['Detail'], row)
        if len(self._rows) > 0 or not self._expect_row_data:
            results['Summary'] = {}
            self._generate_summary(results['Summary'])
        if self._format == 'json-summary':
            answer = {
                'summary': self._summary,
                'metadata': self._jdata['metadata'],
                }
        elif self._format == 'json':
            answer = {
                'summary': self._summary,
                'metadata': self._jdata['metadata'],
                'rows': self._rows
                }
        elif self._format == 'json-verbose':
            answer = deepcopy(self._jdata)
            answer['processed_results'] = {
                'summary': self._summary,
                'rows': self._rows
                }
        return answer

    def __create_text_report(self):
        """
        Create textual report.
        """
        results = {}
        results['Overview'] = {}
        results['Overview']['Job Name'] = self._jdata['metadata']['job_name']
        results['Overview']['Start Time'] = self._jdata['metadata']['cluster_start_time']
        if 'verbose' in self._format and len(self._rows):
            results['Detail'] = {}
            self._rows.sort(key=self.__row_name)
            for row in self._rows:
                self._generate_row(results['Detail'], row)
        if len(self._rows) > 0 or not self._expect_row_data:
            results['Summary'] = {}
            self._generate_summary(results['Summary'])
            results['Overview']['Status'] = 'Success'
        else:
            results['Overview']['Status'] = 'FAILED, no data generated'

        results['Overview']['Workload'] = self._jdata['metadata']['workload']
        results['Overview']['Job UUID'] = self._jdata['metadata']['run_uuid']
        results['Overview']['Run host'] = self._jdata['metadata']['runHost']
        results['Overview']['Artifact Directory'] = self._jdata['metadata'].get('artifact_directory', '')
        results['Overview']['Kubernetes version'] = self._jdata['metadata']['kubernetes_version']['serverVersion']['gitVersion']
        if 'openshiftVersion' in self._jdata['metadata']['kubernetes_version']:
            results['Overview']['OpenShift Version'] = self._jdata['metadata']['kubernetes_version']['openshiftVersion']
        key_width, integer_width = self.__compute_report_width(results)
        cmdline = ' '.join(self._jdata['metadata']['expanded_command_line'])
        if 'parseable' in self._format:
            cmdline = ' '.join(self._jdata['metadata']['expanded_command_line'])
        else:
            cmdline = self._wrap_text(' '.join(self._jdata['metadata']['expanded_command_line']))
        results['Overview']['Command line'] = cmdline
        outfile = io.StringIO()
        self.__print_report(results, outfile=outfile, value_column=key_width, integer_width=integer_width)
        return outfile.getvalue()

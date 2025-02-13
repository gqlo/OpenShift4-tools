#!/usr/bin/env python3
# Copyright 2022-2023 Robert Krawitz/Red Hat
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

import sys
import importlib
import inspect


class ClusterBusterAnalyzeOne:
    def __init__(self, workload: str, data: dict, metadata: dict):
        self._workload = workload
        self._data = data
        self._metadata = metadata

    def _safe_get(self, obj, keys: list, default=None):
        try:
            while keys:
                key = keys[0]
                obj = obj[key]
                keys = keys[1:]
            return obj
        except Exception:
            return default

    def Analyze(self):
        pass


class ClusterBusterAnalysis:
    """
    Analyze ClusterBuster reports
    """
    def __init__(self, data: dict, report_type=None):
        self._data = data
        if report_type is None:
            report_type = 'ci'
        self._report_type = report_type

    @staticmethod
    def list_analysis_formats():
        return ['ci', 'spreadsheet', 'summary', 'raw']

    def __postprocess(self, report, status, metadata):
        import_module = None
        try:
            imported_lib = importlib.import_module(f'..{self._report_type}.analyze_postprocess', __name__)
            for i in inspect.getmembers(imported_lib):
                if i[0] == 'AnalyzePostprocess':
                    import_module = i[1]
                    break
        except Exception:
            pass
        if import_module is not None:
            return import_module(report, status, metadata).Postprocess()
        else:
            return report

    def Analyze(self):
        report = dict()
        metadata = dict()
        status = dict()
        if self._data is None:
            return None
        report_type = None
        if 'metadata' in self._data:
            metadata = self._data['metadata']
        if 'status' in self._data:
            status = self._data['status']
        if self._report_type == 'raw':
            return self._data
        for workload, workload_data in sorted(self._data.items()):
            if workload == 'metadata' or workload == 'status':
                continue
            try:
                imported_lib = importlib.import_module(f'..{self._report_type}.{workload}_analysis', __name__)
            except Exception as exc:
                print(f'Warning: no analyzer for workload {workload} {exc}', file=sys.stderr)
                continue
            try:
                for i in inspect.getmembers(imported_lib):
                    if i[0] == f'{workload}_analysis':
                        report[workload] = i[1](workload, workload_data, metadata).Analyze()
                        if report_type is None:
                            report_type = type(report[workload])
                        elif report_type is not type(report[workload]):
                            raise TypeError(f"Incompatible report types for {workload}: expect {report_type}, found {type(report[workload])}")
            except Exception as exc:
                raise exc
        if report_type == str:
            return self.__postprocess('\n\n'.join([str(v) for v in report.values()]), status, metadata)
        elif report_type == dict or report_type == list:
            report['metadata'] = metadata
            for v in ['uuid', 'run_host', 'openshift_version', 'kata_version', 'kata_containers_version', 'cnv_version']:
                if v in metadata:
                    report['metadata'][v] = metadata[v]
            for v in ['result', 'job_start', 'job_end', 'job_runtime']:
                if v in status:
                    report['metadata'][v] = status[v]
            if 'failed' in status and len(status['failed']) > 0:
                report['metadata']['failed'] = status['failed']
            return self.__postprocess(report, status, metadata)
        elif report_type is None:
            return None
        else:
            raise TypeError(f"Unexpected report type {report_type}, expect either str or dict")

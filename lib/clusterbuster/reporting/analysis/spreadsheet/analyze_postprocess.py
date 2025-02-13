#!/usr/bin/env python3
# Copyright 2023 Robert Krawitz/Red Hat
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


class AnalyzePostprocess:
    """
    Post-process ClusterBuster analysis
    """

    def __init__(self, report, status, metadata):
        self._report = report
        self._status = status
        self._metadata = metadata

    def Postprocess(self):
        metadata = {}
        for job, job_status in self._status['jobs'].items():
            if job not in metadata:
                metadata[job] = {}
            for var in ['result', 'job_start', 'job_end', 'job_runtime']:
                if var in job_status:
                    metadata[job][var] = job_status[var]
        for job, job_metadata in self._metadata['jobs'].items():
            if job not in metadata:
                metadata[job] = {}
            for var in ['uuid', 'run_host', 'openshift_version', 'kata_containers_version', 'kata_version']:
                if var in job_metadata:
                    metadata[job][var] = job_metadata[var]
        meta_answer = ''
        for job, jdata in metadata.items():
            meta_answer += f'{job}:\n'
            meta_answer += '\n'.join([f'\t{key}\t{value}' for key, value in jdata.items()])
            meta_answer += '\n\n'
        return f'{meta_answer}\n{self._report}'

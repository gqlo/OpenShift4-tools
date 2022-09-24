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

from ..summary.files_analysis import FilesAnalysisBase


class files_analysis(FilesAnalysisBase):
    """
    Analyze uperf data
    """

    def __init__(self, workload: str, data: dict, metadata: dict):
        super().__init__(workload, data, metadata)

    def Analyze(self):
        report, detail = super().Analyze(report_detail=True)
        answer = f"""Workload: {report['workload']}
uuid: {report['uuid']}
Times in seconds

Op\tKata\trunc\tratio
"""
        for op in ['create', 'read', 'remove']:
            answer += '\t'.join([op,
                                 self._prettyprint(report['kata'][op]['elapsed_time'], precision=3, base=0),
                                 self._prettyprint(report['runc'][op]['elapsed_time'], precision=3, base=0),
                                 self._prettyprint(report['ratio'][op]['elapsed_time'], precision=3, base=0)]) + '\n'
        answer += """
Ratio
Op\tMin ratio\tAvg ratio\tMax ratio
"""
        for op in ['create', 'read', 'remove']:
            answer += '\t'.join([op,
                                 self._prettyprint(report['min_ratio'][op]['elapsed_time'], precision=3, base=0),
                                 self._prettyprint(report['ratio'][op]['elapsed_time'], precision=3, base=0),
                                 self._prettyprint(report['max_ratio'][op]['elapsed_time'], precision=3, base=0)]) + '\n'
        answer += "\tCreate\t\t\tRead\t\t\tRemove\n"
        answer += "Case\tKata\trunc\tratio\tKata\trunc\tratio\tKata\trunc\tratio\n"
        for case, row in detail.items():
            answer += case
            for op in ['create', 'read', 'remove']:
                for rt in ['kata', 'runc', 'ratio']:
                    answer += '\t' + self._prettyprint(row[op]['elapsed_time'][rt], precision=3, base=0)
            answer += '\n'
        return answer
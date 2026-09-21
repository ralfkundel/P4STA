# Copyright 2019-present Ralf Kundel, Fridolin Siegmund
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from django import template
register = template.Library()


@register.filter
def getkeyvalue(dict, key):
    try:
        return dict[key]
    except Exception:
        return ""


@register.filter
def getbyindex(indexable, i):
    return indexable[i]


def parse_version(v):
    return [int(x) for x in v.split(".")]


def normalize(v1, v2):
    l = max(len(v1), len(v2))
    v1 += [0] * (l - len(v1))
    v2 += [0] * (l - len(v2))
    return v1, v2


@register.filter
def version_gte(v1, v2):
    p1 = parse_version(v1)
    p2 = parse_version(v2)
    p1, p2 = normalize(p1, p2)
    return p1 >= p2
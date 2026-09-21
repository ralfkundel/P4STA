# Copyright 2026-present Fridolin Siegmund, Ralf Kundel
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

from fractions import Fraction
from math import gcd, lcm
from functools import reduce
from typing import Iterable, Union


Percent = Union[int, float, str, Fraction]

# convert values into exact fractions
def to_fraction(value):
    if isinstance(value, Fraction):
        return value

    if isinstance(value, str):
        value = value.strip().replace("%", "").replace(",", ".")
        return Fraction(value)

    return Fraction(str(value))

# converts numeric values into the smallest proportional integer list
# e.g. [25, 75] -> [1, 3]
def smallest_integer_ratio(values):
    fractions = [to_fraction(v) for v in values]

    if not fractions:
        return []

    if any(v < 0 for v in fractions):
        raise ValueError("Values must be non-negative.")

    if all(v == 0 for v in fractions):
        raise ValueError("At least one value must be greater than zero.")

    common_denominator = 1
    for value in fractions:
        common_denominator = lcm(common_denominator, value.denominator)

    integers = [
        value.numerator * (common_denominator // value.denominator)
        for value in fractions
    ]

    divisor = reduce(gcd, (abs(x) for x in integers if x != 0))

    return [x // divisor for x in integers]


def calculate_flow_percentages(flows, known_percentages):
    if len(set(flows)) != len(flows):
        raise ValueError("flow identifiers must be unique")

    # no percentage specified (not in known_percentages dict)
    unknown_flows = [flow for flow in flows if flow not in known_percentages]

    invalid_flows = set(known_percentages) - set(flows)
    if invalid_flows:
        raise ValueError(f"Unknown flows in percentages: {invalid_flows}")

    result = {}

    for flow in flows:
        if flow in known_percentages:
            result[flow] = to_fraction(known_percentages[flow])

    used_percentage = sum(result.values(), Fraction(0))
    remaining_percentage = Fraction(100) - used_percentage

    if remaining_percentage < 0:
        raise ValueError("percentages > 100%")

    if unknown_flows:
        percentage_per_unknown_flow = remaining_percentage / len(unknown_flows)

        for flow in unknown_flows:
            result[flow] = percentage_per_unknown_flow
    else:
        if remaining_percentage != 0:
            raise ValueError(f"Sum of flows != 100% with remaining percentage of {remaining_percentage}")

    return result

# entry function
# e.g.: flows = ["A", "B"] and percentages = {"A": 25} ==> [1, 3]
def calculate_packet_distribution(flows, known_percentages):
    percentages = calculate_flow_percentages(flows, known_percentages)

    ordered_percentages = [
        percentages[flow]
        for flow in flows
    ]

    return smallest_integer_ratio(ordered_percentages)


def calculate_preset_percentages(flow_count, preset):
    if flow_count < 1:
        raise ValueError("No established flows.")

    mode = preset.get("mode")
    if mode == "equal":
        return [Fraction(100, flow_count)] * flow_count
    if mode == "alternating":
        shares = [to_fraction(preset.get(key, ""))
                  for key in ("share_a", "share_b")]
        if any(share < 0 for share in shares):
            raise ValueError("A/B shares must be non-negative.")
        total = shares[0] * ((flow_count + 1) // 2) + shares[1] * (flow_count // 2)
        if total == 0:
            raise ValueError("At least one established flow needs a positive share.")
        return [100 * shares[index % 2] / total for index in range(flow_count)]
    if mode == "priority":
        group_count = to_fraction(preset.get("group_count", ""))
        if group_count.denominator != 1 or not 1 <= group_count < flow_count:
            raise ValueError("Priority group must contain between 1 and "
                             f"{flow_count - 1} flows.")
        group_count = int(group_count)
        group_share = to_fraction(preset.get("group_share", ""))
        if not 0 <= group_share <= 100:
            raise ValueError("Priority group load must be between 0 and 100%.")
        return ([group_share / group_count] * group_count +
                [(100 - group_share) / (flow_count - group_count)] *
                (flow_count - group_count))
    raise ValueError("Unknown traffic preset.")


def smooth_weighted_distribution(weights):
    weights = list(weights)

    if any(weight < 0 for weight in weights):
        raise ValueError("Weights must be non-negative.")

    if any(int(weight) != weight for weight in weights):
        raise ValueError("Weights must be integers.")

    weights = [int(weight) for weight in weights]
    emitted = [0] * len(weights)
    result = []

    for _ in range(sum(weights)):
        best_index = None

        for index, weight in enumerate(weights):
            if weight == 0 or emitted[index] >= weight:
                continue

            if best_index is None:
                best_index = index
            elif emitted[index] * weights[best_index] < emitted[best_index] * weight:
                best_index = index

        result.append(best_index)
        emitted[best_index] += 1

    return result

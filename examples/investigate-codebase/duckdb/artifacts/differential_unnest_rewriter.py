"""Differential check for duckdb PR #19235 (unnest_rewriter pattern 2).

Preserved invariant under test: for every query, the result multiset must be
identical whether the unnest_rewriter rule runs or not.  The rule is a plan
rewrite; it is allowed to change the plan, never the answer.
"""
import duckdb, itertools, sys

SETUP = """
CREATE TABLE with_array(foo INT, arr DOUBLE[]);
INSERT INTO with_array VALUES (1,[1,2,3]),(2,[4,5,6]);
CREATE TABLE edge(foo INT, arr DOUBLE[]);
INSERT INTO edge VALUES (1,[]),(2,NULL),(3,[7]),(4,[NULL]),(5,[1,NULL,3]);
CREATE TABLE strs(k INT, s VARCHAR[]);
INSERT INTO strs VALUES (1,['a','b']),(2,[]),(3,['c']);
"""

QUERIES = {
 "q1_basic":            "SELECT foo, value FROM with_array CROSS JOIN unnest(arr) AS values(value)",
 "q2_ordinality":       "SELECT foo, value, ord FROM with_array CROSS JOIN unnest(arr) WITH ORDINALITY AS values(value, ord)",
 "q3_empty_and_null":   "SELECT foo, value FROM edge CROSS JOIN unnest(arr) AS values(value)",
 "q4_left_join_style":  "SELECT foo, value FROM edge LEFT JOIN unnest(arr) AS values(value) ON true",
 "q5_where_filter":     "SELECT foo, value FROM with_array CROSS JOIN unnest(arr) AS values(value) WHERE value > 2",
 "q6_agg":              "SELECT foo, sum(value) FROM with_array CROSS JOIN unnest(arr) AS values(value) GROUP BY foo",
 "q7_two_unnests":      "SELECT a.foo, a.value, b.value FROM (SELECT foo, value FROM with_array CROSS JOIN unnest(arr) AS values(value)) a, (SELECT foo, value FROM with_array CROSS JOIN unnest(arr) AS values(value)) b WHERE a.foo=b.foo",
 "q8_strings":          "SELECT k, s2 FROM strs CROSS JOIN unnest(s) AS t(s2)",
 "q9_nested_subquery":  "SELECT foo, (SELECT count(*) FROM unnest(w.arr)) c FROM with_array w",
 "q10_correlated_agg":  "SELECT foo, list(value) FROM with_array CROSS JOIN unnest(arr) AS values(value) GROUP BY foo ORDER BY foo",
 "q11_ordinality_filter":"SELECT foo, value, ord FROM with_array CROSS JOIN unnest(arr) WITH ORDINALITY AS values(value, ord) WHERE ord = 2",
 "q12_edge_ordinality": "SELECT foo, value, ord FROM edge CROSS JOIN unnest(arr) WITH ORDINALITY AS values(value, ord)",
}

def run(rule_on: bool):
    con = duckdb.connect()
    con.execute(SETUP)
    if not rule_on:
        con.execute("SET disabled_optimizers='unnest_rewriter'")
    out = {}
    for name, q in QUERIES.items():
        try:
            rows = con.execute(q).fetchall()
            out[name] = ("OK", sorted(rows, key=repr))
        except Exception as e:                       # noqa: BLE001 - we compare failures too
            out[name] = ("ERR", f"{type(e).__name__}: {e}")
    plans = {}
    for name, q in QUERIES.items():
        try:
            plans[name] = con.execute("EXPLAIN " + q).fetchall()[0][1]
        except Exception as e:                       # noqa: BLE001
            plans[name] = f"ERR {e}"
    con.close()
    return out, plans

on, plan_on   = run(True)
off, plan_off = run(False)

print(f"duckdb {duckdb.__version__}\n")
print(f"{'query':<24}{'result equal?':<16}{'plan changed?':<16}{'DELIM_JOIN on/off'}")
print("-" * 78)
fails = 0
for name in QUERIES:
    same = on[name] == off[name]
    plan_changed = plan_on[name] != plan_off[name]
    d_on  = "yes" if "DELIM_JOIN" in plan_on[name] else "no"
    d_off = "yes" if "DELIM_JOIN" in plan_off[name] else "no"
    if not same:
        fails += 1
    print(f"{name:<24}{('SAME' if same else '*** DIFFERENT ***'):<16}"
          f"{('changed' if plan_changed else 'identical'):<16}{d_on}/{d_off}")
print("-" * 78)
print(f"queries: {len(QUERIES)}   invariant violations: {fails}")
sys.exit(1 if fails else 0)

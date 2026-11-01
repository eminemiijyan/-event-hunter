import runpy

# The old broad Suitrip endpoint times out from GitHub Actions.  Keep this workflow
# slot as an aggregate smoke test for the official municipal West-Gifu sources.
runpy.run_path('tests/test_ogaki_family.py', run_name='__main__')
runpy.run_path('tests/test_ibigawa_kanko.py', run_name='__main__')
runpy.run_path('tests/test_anpachi_events.py', run_name='__main__')
print('PASS')

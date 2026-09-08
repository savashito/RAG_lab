def pytest_configure(config):
    config.addinivalue_line(
        'markers',
        'corpus: prueba que requiere el corpus real en ingestion/out (se salta si falta)',
    )

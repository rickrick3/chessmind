def pytest_sessionfinish(session, exitstatus):
    from analysis.engine import close_engine

    close_engine()

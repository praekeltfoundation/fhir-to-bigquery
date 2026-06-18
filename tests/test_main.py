from fhir_to_bigquery.main import main


def test_main_prints_startup_message(capsys):
    main()

    captured = capsys.readouterr()
    assert captured.out == "Hello from fhir-to-bigquery!\n"

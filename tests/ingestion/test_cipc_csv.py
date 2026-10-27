"""CIPC CSV loader. Every name, number and key here is invented."""

from datetime import date
from pathlib import Path

import pytest

from ingestion.cipc_csv import COMPANY_COLUMNS, DIRECTOR_COLUMNS, CipcCsvError, load_cipc

EXAMPLES = Path(__file__).resolve().parents[2] / "examples" / "cipc"
COMPANY = "etenders:900001,FICTIONAL SUPPLIES (PTY) LTD,2019/123456/07,2019-06-03,In Business,Human health activities,2021-06-29;2020-06-30,2026-10-27"  # noqa: E501
DIRECTOR = "etenders:900001,dir-0001,A. Fictional Person,2019-06-03,,1980-01-01"


def write(tmp_path: Path, companies: list[str], directors: list[str]) -> Path:
    (tmp_path / "companies.csv").write_text(
        "\n".join([",".join(COMPANY_COLUMNS), *companies]) + "\n", encoding="utf-8"
    )
    (tmp_path / "directors.csv").write_text(
        "\n".join([",".join(DIRECTOR_COLUMNS), *directors]) + "\n", encoding="utf-8"
    )
    return tmp_path


def errors_for(tmp_path: Path, companies: list[str], directors: list[str]) -> str:
    with pytest.raises(CipcCsvError) as err:
        load_cipc(write(tmp_path, companies, directors))
    return str(err.value)


def test_loads_companies_and_directors(tmp_path: Path) -> None:
    data = load_cipc(write(tmp_path, [COMPANY], [DIRECTOR]))

    record = data.records["etenders:900001"]
    assert record.company.registration_number == "2019/123456/07"
    assert record.company.registration_date == date(2019, 6, 3)
    assert record.company.status == "In Business"
    assert record.company.industry == "Human health activities"
    assert record.company.annual_return_dates == (date(2020, 6, 30), date(2021, 6, 29))
    assert record.checked_on == date(2026, 10, 27)
    (director,) = data.directors["etenders:900001"]
    assert (director.director_id, director.full_name) == ("dir-0001", "A. Fictional Person")
    assert director.appointed == date(2019, 6, 3) and director.resigned is None
    assert director.birth_date == date(1980, 1, 1)


def test_blank_annual_returns_mean_unknown_and_none_means_never_filed(tmp_path: Path) -> None:
    unknown = COMPANY.replace("2021-06-29;2020-06-30", "")
    never = (
        COMPANY.replace("900001", "900002")
        .replace("123456", "654321")
        .replace("2021-06-29;2020-06-30", "none")
    )

    data = load_cipc(write(tmp_path, [unknown, never], []))

    assert data.records["etenders:900001"].company.annual_return_dates is None
    assert data.records["etenders:900002"].company.annual_return_dates == ()


def test_a_company_with_no_directors_has_an_empty_list(tmp_path: Path) -> None:
    data = load_cipc(write(tmp_path, [COMPANY], []))

    assert data.directors["etenders:900001"] == ()


def test_enriched_company_keeps_the_etenders_name(tmp_path: Path) -> None:
    data = load_cipc(write(tmp_path, [COMPANY], []))

    company = data.company("etenders:900001", "Fictional Supplies")
    assert company is not None
    assert company.name == "Fictional Supplies"
    assert company.registration_number == "2019/123456/07"
    assert data.company("etenders:999999", "Anyone") is None


def test_the_committed_examples_are_valid(tmp_path: Path) -> None:
    data = load_cipc(EXAMPLES)

    assert len(data.records) == 3
    # The same person directs two example companies, so R4 has a network to find.
    assert {d.director_id for ds in data.directors.values() for d in ds} == {
        "dir-0001",
        "dir-0002",
        "dir-0003",
    }
    # Example keys can never collide with a real eTenders supplier id (digits only).
    assert all(cid.startswith("etenders:example-") for cid in data.records)


@pytest.mark.parametrize(
    ("row", "message"),
    [
        (COMPANY.replace("2019/123456/07", "2019-123456-07"), "not like 2019/123456/07"),
        (COMPANY.replace("etenders:900001", "900001"), "not an eTenders supplier key"),
        (COMPANY.replace(",2019-06-03,", ",03/06/2019,"), "not a YYYY-MM-DD date"),
        (COMPANY.replace(",2019-06-03,", ",2999-01-01,"), "not a plausible date"),
        (COMPANY.replace("FICTIONAL SUPPLIES (PTY) LTD", ""), "cipc_name is required"),
        (COMPANY.replace(",2026-10-27", ","), "checked_on is required"),
        (COMPANY.replace("2021-06-29;2020-06-30", "2018-01-01"), "predates registration"),
        (COMPANY + ",extra", "more values than columns"),
    ],
)
def test_bad_company_rows_are_rejected(tmp_path: Path, row: str, message: str) -> None:
    assert message in errors_for(tmp_path, [row], [])


def test_duplicate_companies_and_registration_numbers_are_rejected(tmp_path: Path) -> None:
    same_id = COMPANY.replace("123456", "111111")
    same_number = COMPANY.replace("900001", "900002")

    text = errors_for(tmp_path, [COMPANY, same_id, same_number], [])

    assert "company_id etenders:900001 appears twice" in text
    assert "registration_number 2019/123456/07 is also on line 2" in text


@pytest.mark.parametrize(
    ("row", "message"),
    [
        (DIRECTOR.replace("900001", "900009"), "is not in companies.csv"),
        (DIRECTOR.replace("dir-0001", "8001015009087"), "looks like an ID number"),
        (DIRECTOR.replace("1980-01-01", "2020-01-01"), "director under 16"),
        (
            DIRECTOR.replace("2019-06-03", "1990-01-01").replace("1980-01-01", "1995-01-01"),
            "birth_date is not before appointed",
        ),
        (DIRECTOR.replace("1980-01-01", "01/01/1980"), "not a YYYY-MM-DD date"),
        (DIRECTOR.replace("dir-0001", "Dir 1"), "must be like dir-0001"),
        (DIRECTOR.replace("A. Fictional Person", ""), "full_name is required"),
        (DIRECTOR.replace("2019-06-03,", "2019-06-03,2019-01-01"), "resigned is before appointed"),
    ],
)
def test_bad_director_rows_are_rejected(tmp_path: Path, row: str, message: str) -> None:
    assert message in errors_for(tmp_path, [COMPANY], [row])


def test_a_director_listed_twice_for_one_company_is_rejected(tmp_path: Path) -> None:
    text = errors_for(tmp_path, [COMPANY], [DIRECTOR, DIRECTOR])

    assert "already listed for etenders:900001 on line 2" in text


def test_one_director_id_must_mean_one_person(tmp_path: Path) -> None:
    other = COMPANY.replace("900001", "900002").replace("123456", "654321")
    renamed = DIRECTOR.replace("900001", "900002").replace("A. Fictional", "Z. Fictional")

    text = errors_for(tmp_path, [COMPANY, other], [DIRECTOR, renamed])

    assert "director dir-0001 has a different name on line 2" in text


def test_every_problem_is_reported_at_once(tmp_path: Path) -> None:
    bad_number = COMPANY.replace("2019/123456/07", "bad")
    bad_date = COMPANY.replace("900001", "900002").replace(",2019-06-03,", ",soon,")

    text = errors_for(tmp_path, [bad_number, bad_date], [])

    assert "2 problem(s)" in text
    assert "line 2:" in text and "line 3:" in text


def test_a_wrong_header_is_rejected(tmp_path: Path) -> None:
    (tmp_path / "companies.csv").write_text("company_id,name\n", encoding="utf-8")

    with pytest.raises(CipcCsvError, match="header must be exactly"):
        load_cipc(tmp_path)


def test_a_missing_file_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(CipcCsvError, match=r"companies.csv: 1 problem"):
        load_cipc(tmp_path)


def test_a_file_saved_in_the_windows_code_page_is_rejected_clearly(tmp_path: Path) -> None:
    write(tmp_path, [], [])
    header = ",".join(COMPANY_COLUMNS)
    row = COMPANY.replace("FICTIONAL SUPPLIES", "FICTIONAL CAFÉ SUPPLIES")
    (tmp_path / "companies.csv").write_bytes(f"{header}\n{row}\n".encode("cp1252"))

    with pytest.raises(CipcCsvError, match="CSV UTF-8"):
        load_cipc(tmp_path)


def test_a_utf8_file_with_excel_bom_and_accents_loads(tmp_path: Path) -> None:
    write(tmp_path, [], [])
    header = ",".join(COMPANY_COLUMNS)
    row = COMPANY.replace("FICTIONAL SUPPLIES", "FICTIONAL CAFÉ SUPPLIES")
    (tmp_path / "companies.csv").write_text(f"{header}\n{row}\n", encoding="utf-8-sig")

    data = load_cipc(tmp_path)

    assert data.records["etenders:900001"].cipc_name == "FICTIONAL CAFÉ SUPPLIES (PTY) LTD"


@pytest.mark.parametrize(
    "id_number",
    ["8001015009087", "800101 5009 087", "800101-5009-087"],
)
def test_an_id_number_in_any_cell_is_rejected_without_repeating_it(
    tmp_path: Path, id_number: str
) -> None:
    in_name = DIRECTOR.replace("A. Fictional Person", f"A. Fictional Person {id_number}")
    in_status = COMPANY.replace("In Business", id_number)

    text = errors_for(tmp_path, [in_status], [])
    assert "status holds what looks like an ID number" in text
    assert id_number not in text

    text = errors_for(tmp_path, [COMPANY], [in_name])
    assert "full_name holds what looks like an ID number" in text
    assert id_number not in text


def test_registration_numbers_and_dates_are_not_mistaken_for_id_numbers(tmp_path: Path) -> None:
    data = load_cipc(write(tmp_path, [COMPANY], [DIRECTOR]))

    assert "etenders:900001" in data.records


def test_a_blank_birth_date_is_unknown(tmp_path: Path) -> None:
    row = DIRECTOR.replace("1980-01-01", "")

    data = load_cipc(write(tmp_path, [COMPANY], [row]))

    assert data.directors["etenders:900001"][0].birth_date is None


def test_one_director_id_must_have_one_birth_date(tmp_path: Path) -> None:
    other = COMPANY.replace("900001", "900002").replace("123456", "654321")
    second = DIRECTOR.replace("900001", "900002").replace("1980-01-01", "1981-01-01")

    text = errors_for(tmp_path, [COMPANY, other], [DIRECTOR, second])

    assert "director dir-0001 has a different birth_date on line 2" in text


def test_dates_separated_by_spaces_are_not_mistaken_for_an_id_number(tmp_path: Path) -> None:
    row = COMPANY.replace("2021-06-29;2020-06-30", "2020-06-30 2021-06-29")

    text = errors_for(tmp_path, [row], [])

    assert "ID number" not in text
    assert "annual_return_dates" in text

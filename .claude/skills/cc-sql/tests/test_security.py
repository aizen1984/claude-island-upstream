"""安全校验测试（含 SELECT * 检测、聚合查询检测）"""
import pytest

from core.exceptions import AggregateError, SecurityError, SelectStarError
from core.security import (
    check_aggregate_query,
    check_select_star,
    validate_and_prepare_sql,
    validate_sql,
)


class TestValidateSql:
    """基础安全校验"""

    def test_valid_select(self):
        ok, msg = validate_sql("SELECT id, name FROM users LIMIT 10")
        assert ok is True

    def test_valid_show(self):
        ok, msg = validate_sql("SHOW TABLES")
        assert ok is True

    def test_valid_describe(self):
        ok, msg = validate_sql("DESCRIBE users")
        assert ok is True

    def test_valid_explain(self):
        ok, msg = validate_sql("EXPLAIN SELECT id FROM users")
        assert ok is True

    def test_empty_sql(self):
        ok, msg = validate_sql("")
        assert ok is False

    def test_whitespace_sql(self):
        ok, msg = validate_sql("   ")
        assert ok is False

    def test_reject_insert(self):
        ok, msg = validate_sql("INSERT INTO users VALUES (1, 'test')")
        assert ok is False
        assert "INSERT" in msg

    def test_reject_update(self):
        ok, msg = validate_sql("UPDATE users SET name='test'")
        assert ok is False

    def test_reject_delete(self):
        ok, msg = validate_sql("DELETE FROM users")
        assert ok is False

    def test_reject_drop(self):
        ok, msg = validate_sql("DROP TABLE users")
        assert ok is False

    def test_reject_multi_statement(self):
        ok, msg = validate_sql("SELECT 1; DROP TABLE users")
        assert ok is False

    def test_reject_into_outfile(self):
        ok, msg = validate_sql("SELECT * INTO OUTFILE '/tmp/test'")
        assert ok is False

    def test_reject_comment_injection(self):
        ok, msg = validate_sql("SELECT 1 -- ")
        assert ok is False


class TestCheckSelectStar:
    """SELECT * 检测"""

    def test_detect_select_star(self):
        has_star, msg = check_select_star("SELECT * FROM users")
        assert has_star is True

    def test_detect_select_star_with_where(self):
        has_star, msg = check_select_star("SELECT * FROM users WHERE id = 1")
        assert has_star is True

    def test_allow_count_star(self):
        has_star, msg = check_select_star("SELECT COUNT(*) FROM users")
        assert has_star is False

    def test_allow_specific_columns(self):
        has_star, msg = check_select_star("SELECT id, name FROM users")
        assert has_star is False

    def test_allow_exists_subquery_star(self):
        has_star, msg = check_select_star(
            "SELECT id FROM users WHERE EXISTS (SELECT * FROM orders)"
        )
        assert has_star is False

    def test_allow_in_subquery_star(self):
        has_star, msg = check_select_star(
            "SELECT id FROM users WHERE id IN (SELECT * FROM ids)"
        )
        assert has_star is False


class TestValidateAndPrepareSql:
    """一站式校验"""

    def test_normal_select(self):
        result = validate_and_prepare_sql("SELECT id FROM users LIMIT 10")
        assert "LIMIT 10" in result

    def test_auto_limit(self):
        result = validate_and_prepare_sql("SELECT id FROM users", max_rows=500)
        assert "LIMIT 500" in result

    def test_strip_semicolons(self):
        result = validate_and_prepare_sql("SELECT id FROM users LIMIT 10;")
        assert not result.endswith(";")

    def test_show_no_limit(self):
        result = validate_and_prepare_sql("SHOW TABLES")
        assert "LIMIT" not in result

    def test_describe_no_limit(self):
        result = validate_and_prepare_sql("DESCRIBE users")
        assert "LIMIT" not in result

    def test_reject_dangerous_sql(self):
        with pytest.raises(SecurityError):
            validate_and_prepare_sql("DROP TABLE users")

    def test_reject_select_star_default(self):
        with pytest.raises(SelectStarError):
            validate_and_prepare_sql("SELECT * FROM users")

    def test_allow_select_star_when_configured(self):
        result = validate_and_prepare_sql(
            "SELECT * FROM users", allow_select_star=True
        )
        assert "SELECT *" in result

    def test_preserve_existing_limit(self):
        result = validate_and_prepare_sql("SELECT id FROM users LIMIT 5", max_rows=1000)
        assert "LIMIT 5" in result
        assert "LIMIT 1000" not in result

    def test_reject_aggregate_without_where(self):
        with pytest.raises(AggregateError):
            validate_and_prepare_sql("SELECT COUNT(id) FROM users")

    def test_allow_aggregate_with_where(self):
        result = validate_and_prepare_sql(
            "SELECT COUNT(id) FROM users WHERE status = 1"
        )
        assert "COUNT" in result


class TestCheckAggregateQuery:
    """聚合查询检测"""

    def test_reject_count_without_where(self):
        has_violation, msg = check_aggregate_query("SELECT COUNT(id) FROM users")
        assert has_violation is True

    def test_reject_sum_without_where(self):
        has_violation, msg = check_aggregate_query("SELECT SUM(amount) FROM orders")
        assert has_violation is True

    def test_reject_avg_without_where(self):
        has_violation, msg = check_aggregate_query("SELECT AVG(price) FROM products")
        assert has_violation is True

    def test_reject_min_without_where(self):
        has_violation, msg = check_aggregate_query("SELECT MIN(id) FROM users")
        assert has_violation is True

    def test_reject_max_without_where(self):
        has_violation, msg = check_aggregate_query("SELECT MAX(id) FROM users")
        assert has_violation is True

    def test_reject_group_by_without_where(self):
        has_violation, msg = check_aggregate_query(
            "SELECT status, COUNT(id) FROM users GROUP BY status"
        )
        assert has_violation is True

    def test_allow_count_with_where(self):
        has_violation, msg = check_aggregate_query(
            "SELECT COUNT(id) FROM users WHERE created_at > '2024-01-01'"
        )
        assert has_violation is False

    def test_allow_sum_with_where(self):
        has_violation, msg = check_aggregate_query(
            "SELECT SUM(amount) FROM orders WHERE user_id = 123"
        )
        assert has_violation is False

    def test_allow_group_by_with_where(self):
        has_violation, msg = check_aggregate_query(
            "SELECT status, COUNT(id) FROM users WHERE org_id = 1 GROUP BY status"
        )
        assert has_violation is False

    def test_allow_non_aggregate_without_where(self):
        has_violation, msg = check_aggregate_query("SELECT id, name FROM users LIMIT 10")
        assert has_violation is False

    def test_skip_show_statement(self):
        has_violation, msg = check_aggregate_query("SHOW TABLES")
        assert has_violation is False

    def test_skip_describe_statement(self):
        has_violation, msg = check_aggregate_query("DESCRIBE users")
        assert has_violation is False

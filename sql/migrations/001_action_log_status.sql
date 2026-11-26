-- Bổ sung trạng thái cho dss_action_log. Chạy lại được nhiều lần; không xoá bản ghi cũ.
ALTER TABLE dss_action_log
    ADD COLUMN IF NOT EXISTS status VARCHAR(20),
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ;

ALTER TABLE dss_action_log ALTER COLUMN status SET DEFAULT 'recorded';
UPDATE dss_action_log SET status = 'recorded' WHERE status IS NULL;
UPDATE dss_action_log SET updated_at = created_at WHERE updated_at IS NULL;
ALTER TABLE dss_action_log ALTER COLUMN status SET NOT NULL;

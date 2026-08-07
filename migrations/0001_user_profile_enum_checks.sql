-- 0001: user_profiles / user_learning_goals 의 enum 값 CHECK 제약 추가
--
-- 배경: app/models/user.py 의 gender / study_frequency / goal 컬럼을 str Enum 타입으로
--   매핑했다. 저장 타입은 그대로 varchar 이므로 컬럼 변경은 필요 없고, 값 범위를 강제하는
--   CHECK 제약만 추가하면 된다.
--
-- init_db() 의 create_all 은 "없는 테이블"만 만들고 기존 테이블의 제약 변경은 반영하지
-- 않는다. 두 테이블은 이미 생성돼 있으므로 이 스크립트를 한 번 직접 실행해야 한다.
--
-- 적용 시점 데이터: 두 테이블 모두 0건이라 기존 값 정리(백필)는 필요 없었다.
-- 값이 있는 환경에 적용한다면 먼저 아래로 위반 행을 확인할 것:
--   select distinct gender from user_profiles
--    where gender is not null
--      and gender not in ('male','female','other','prefer_not_to_say');
--
-- 실행:
--   psql "$DATABASE_URL" -f migrations/0001_user_profile_enum_checks.sql

BEGIN;

ALTER TABLE user_profiles
    DROP CONSTRAINT IF EXISTS ck_user_profiles_gender;
ALTER TABLE user_profiles
    ADD CONSTRAINT ck_user_profiles_gender
    CHECK (gender IN ('male', 'female', 'other', 'prefer_not_to_say'));

ALTER TABLE user_profiles
    DROP CONSTRAINT IF EXISTS ck_user_profiles_study_frequency;
ALTER TABLE user_profiles
    ADD CONSTRAINT ck_user_profiles_study_frequency
    CHECK (study_frequency IN ('daily', 'five_per_week', 'three_per_week', 'twice_per_week', 'weekly'));

ALTER TABLE user_learning_goals
    DROP CONSTRAINT IF EXISTS ck_user_learning_goals_goal;
ALTER TABLE user_learning_goals
    ADD CONSTRAINT ck_user_learning_goals_goal
    CHECK (goal IN ('daily_conversation', 'business', 'travel', 'exam', 'culture', 'other'));

COMMIT;

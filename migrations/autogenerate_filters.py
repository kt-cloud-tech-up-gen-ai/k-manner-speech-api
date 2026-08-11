"""autogenerate 비교에서 제외할 객체 정의.

`app.core.db.enum_column`은 Enum을 `native_enum=False, create_constraint=True`로 매핑한다.
이때 CHECK 제약은 DDL을 낼 때 Enum 타입이 만들어내며, 모델 메타데이터에는 테이블 레벨
제약으로 존재하지 않는다. 반면 DB에서는 reflect되므로 autogenerate가 "DB에만 있는 제약"으로
보고 매번 삭제 diff를 만든다. 실제 불일치가 아니므로 비교 대상에서 뺀다.

이 프로젝트는 손으로 작성한 CHECK 제약을 쓰지 않으므로 type 단위로 제외해도 안전하다.
직접 만든 CHECK를 추가하게 되면 이 필터를 이름 기준으로 좁혀야 한다.
"""


def include_object(object_, name, type_, reflected, compare_to) -> bool:
    if type_ == "check_constraint":
        return False
    return True

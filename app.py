import json
import streamlit as st
from google import genai
from PIL import Image

# ---------------------------------------------------------
# 1. 화성여객 직급별 봉급표 & 일당제 통합 데이터
# ---------------------------------------------------------
JOB_DATA = {
    "중형기사 (버스)": {
        "regular": {
            "type": "hourly_add",
            "base": 1600000,
            "rate": 190000,
        },  # 20시간 이상[cite: 1]
        "daily": {
            "type": "hourly_only",
            "base": 0,
            "rate": 190000,
        },  # 20시간 미만[cite: 1]
    },
    "대형기사 (버스)": {
        "regular": {
            "type": "hourly_add",
            "base": 2300000,
            "rate": 200000,
        },  #[cite: 1]
        "daily": {
            "type": "hourly_only",
            "base": 0,
            "rate": 210000,
        },  #[cite: 1]
    },
    "일반기사 (택시)": {
        "regular": {
            "type": "taxi_rate",
            "base": 3375000,
            "rate": 0.60,
        },  #[cite: 1]
        "daily": {
            "type": "hourly_only",
            "base": 0,
            "rate": 190000,
        },  #[cite: 1]
    },
    "블랙기사 (택시)": {
        "regular": {
            "type": "taxi_rate",
            "base": 4100000,
            "rate": 0.70,
        },  #[cite: 1]
        "daily": {
            "type": "hourly_only",
            "base": 0,
            "rate": 210000,
        },  #[cite: 1]
    },
    "과장 (운영본부)": {
        "regular": {
            "type": "hourly_add",
            "base": 3200000,
            "rate": 210000,
        },  #[cite: 1]
        "daily": {
            "type": "hourly_only",
            "base": 0,
            "rate": 220000,
        },  #[cite: 1]
    },
    "부장": {
        "regular": {
            "type": "hourly_add",
            "base": 3900000,
            "rate": 225000,
        },  #[cite: 1]
        "daily": {
            "type": "hourly_only",
            "base": 0,
            "rate": 235000,
        },  #[cite: 1]
    },
}

st.set_page_config(page_title="화성여객 월급 계산기", layout="centered")
st.title("🚌 화성여객 자동 월급 계산기")

# API 키 설정 (웹 설정 비밀키가 있으면 자동 연결, 없으면 사이드바에서 받음)
secret_key = st.secrets.get("GEMINI_API_KEY", "")
if secret_key:
    api_key = secret_key
else:
    api_key = st.sidebar.text_input("Gemini API Key 입력", type="password")

selected_job = st.selectbox("직급을 선택하세요", list(JOB_DATA.keys()))
is_dual = st.checkbox(
    "행정직/기사직 겸직 여부 (+1,800,000원)"
)  #[cite: 1]

uploaded_files = st.file_uploader(
    "근무표 / 수입 지출 사진을 올려주세요 (여러 장 가능)",
    type=["png", "jpg", "jpeg"],
    accept_multiple_files=True,
)


def parse_time_to_minutes(time_str):
    try:
        parts = str(time_str).strip().split(":")
        hours = int(parts[0])
        minutes = int(parts[1]) if len(parts) > 1 else 0
        return hours * 60 + minutes
    except:
        return 0


if st.button("월급 계산하기") and uploaded_files:
    if not api_key:
        st.error("Gemini API Key를 입력해 주세요.")
        st.stop()

    client = genai.Client(api_key=api_key)
    total_minutes = 0
    total_extracted_income = 0
    total_extracted_expense = 0

    with st.spinner("이미지 분석 및 계산 중..."):
        for file in uploaded_files:
            image = Image.open(file)

            prompt = """
            이 이미지에서 '근무 시간', '수익', '지출' 표 데이터를 추출해줘.
            '위에 포함' 이라는 단어가 있으면 0으로 처리해줘.
            시간은 HH:MM 형식을 유지해줘.
            응답은 반드시 아래 형식의 JSON 배열로만 작성해줘:
            [
              {"time": "2:05", "income": 276400, "expense": 126638},
              {"time": "0:33", "income": 374700, "expense": 296294}
            ]
            """

            response = client.models.generate_content(
                model="gemini-2.5-flash", contents=[image, prompt]
            )

            clean_json = (
                response.text.replace("```json", "")
                .replace("```", "")
                .strip()
            )
            rows = json.loads(clean_json)

            for row in rows:
                total_minutes += parse_time_to_minutes(row.get("time", "0:00"))
                total_extracted_income += int(row.get("income", 0))
                total_extracted_expense += int(row.get("expense", 0))

    calculated_hours = total_minutes // 60  # '분' 절사
    remaining_minutes = total_minutes % 60

    if calculated_hours < 20:
        mode_text = "일당제 (20시간 미만 근무)"
        rule = JOB_DATA[selected_job]["daily"]
        st.info(
            f"💡 총 근무시간이 20시간 미만({calculated_hours}시간)이므로 **일당제 시급**이 적용됩니다."
        )
    else:
        mode_text = "일반 봉급표 (20시간 이상 근무)"
        rule = JOB_DATA[selected_job]["regular"]
        st.success(
            f"✅ 총 근무시간이 20시간 이상({calculated_hours}시간)이므로 **일반 봉급표 기준**이 적용됩니다."
        )

    base_salary = rule["base"]
    if is_dual:
        base_salary += 1800000  #[cite: 1]

    added_salary = 0
    if rule["type"] in ["hourly_add", "hourly_only"]:
        added_salary = calculated_hours * rule["rate"]
    elif rule["type"] == "taxi_rate":
        added_salary = int(total_extracted_income * rule["rate"])

    total_gross = base_salary + added_salary
    final_pay = total_gross + total_extracted_expense  # 지출 전액 환급(+)

    col1, col2, col3 = st.columns(3)
    col1.metric(
        "총 운행시간",
        f"{calculated_hours}시간 {remaining_minutes}분",
        f"시급 계산: {calculated_hours}시간",
    )
    col2.metric("인식된 총 수익", f"{total_extracted_income:,} 원")
    col3.metric("인식된 총 지출 (환급)", f"{total_extracted_expense:,} 원")

    st.divider()

    st.subheader("📌 상세 산정 내역")
    st.write(f"- **선택 직급**: {selected_job}")
    st.write(f"- **적용 조건**: {mode_text}")
    st.write(f"- **기본급 (+겸직수당)**: {base_salary:,} 원")

    if rule["type"] in ["hourly_add", "hourly_only"]:
        st.write(
            f"- **시급 계산**: {calculated_hours}시간 × {rule['rate']:,}원 = {added_salary:,} 원"
        )
    elif rule["type"] == "taxi_rate":
        st.write(
            f"- **택시 수입 배분액**: {total_extracted_income:,}원 × {int(rule['rate']*100)}% = {added_salary:,} 원"
        )

    st.write(f"- **급여 합계**: {total_gross:,} 원")
    st.write(f"- **지출 전액 환급금**: +{total_extracted_expense:,} 원")

    st.markdown(f"### 💰 예상 실수령액: **{final_pay:,} 원**")

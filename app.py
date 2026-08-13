import json
import streamlit as st
from google import genai
from PIL import Image

# 클립보드 붙여넣기 라이브러리
try:
    from streamlit_paste_button import paste_image_button as pbutton

    HAS_PASTE_BUTTON = True
except ImportError:
    HAS_PASTE_BUTTON = False

DEFAULT_API_KEY = "AQ.Ab8RN6KUvxFTsXTeujKulc0gJ_lOH3ubIx0VgHVa5BfdelCKVw"

st.set_page_config(page_title="화성여객 월급 계산기", layout="centered")
st.title("🚌 화성여객 자동 월급 계산기")

# ---------------------------------------------------------
# 1. 화성여객 직급별 봉급표 & 일당제 통합 데이터
# ---------------------------------------------------------
JOB_DATA = {
    "중형기사 (버스)": {
        "regular": {"type": "hourly_add", "base": 1600000, "rate": 190000},
        "daily": {"type": "hourly_only", "base": 0, "rate": 190000},
    },
    "대형기사 (버스)": {
        "regular": {"type": "hourly_add", "base": 2300000, "rate": 200000},
        "daily": {"type": "hourly_only", "base": 0, "rate": 210000},
    },
    "일반기사 (택시)": {
        "regular": {"type": "taxi_rate", "base": 3375000, "rate": 0.60},
        "daily": {"type": "hourly_only", "base": 0, "rate": 190000},
    },
    "블랙기사 (택시)": {
        "regular": {"type": "taxi_rate", "base": 4100000, "rate": 0.70},
        "daily": {"type": "hourly_only", "base": 0, "rate": 210000},
    },
    "과장 (운영본부)": {
        "regular": {"type": "hourly_add", "base": 3200000, "rate": 210000},
        "daily": {"type": "hourly_only", "base": 0, "rate": 220000},
    },
    "부장": {
        "regular": {"type": "hourly_add", "base": 3900000, "rate": 225000},
        "daily": {"type": "hourly_only", "base": 0, "rate": 235000},
    },
}

# ---------------------------------------------------------
# 2. 사이드바 API Key 안내 및 설정
# ---------------------------------------------------------
st.sidebar.subheader("🔑 Gemini API Key")
st.sidebar.info("기본 API Key가 자동으로 입력되어 있습니다.")
sidebar_key = st.sidebar.text_input(
    "API Key 확인/수정", value=DEFAULT_API_KEY, type="default"
)

st.sidebar.caption("👇 복사해서 쓸 수 있는 내 API Key")
st.sidebar.code(DEFAULT_API_KEY, language="text")

secret_key = st.secrets.get("GEMINI_API_KEY", "")
api_key = (
    sidebar_key
    if sidebar_key
    else (secret_key if secret_key else DEFAULT_API_KEY)
).strip()

# ---------------------------------------------------------
# 3. 메인 화면 조건 선택
# ---------------------------------------------------------
selected_job = st.selectbox("직급을 선택하세요", list(JOB_DATA.keys()))
is_dual = st.checkbox("행정직/기사직 겸직 여부 (+1,800,000원)")

# ---------------------------------------------------------
# 4. 이미지 입력 영역
# ---------------------------------------------------------
st.write("---")
st.subheader("📸 근무표 / 수입·지출 이미지 업로드")

pasted_image = None

# 클립보드 붙여넣기 영역 (requirements.txt에 streamlit-paste-button 없을 시 안내문)
if HAS_PASTE_BUTTON:
    st.markdown("### 📋 1단계: 복사한 이미지 바로 붙여넣기")
    st.caption("캡처한 뒤 아래 버튼을 누르면 즉시 들어옵니다.")

    paste_result = pbutton(
        label="📋 클립보드 이미지 붙여넣기 (클릭 1번으로 완성)",
        text_color="#ffffff",
        background_color="#27ae60",
        hover_background_color="#2ecc71",
        key="paste_image_btn",
    )
    if paste_result.image_data is not None:
        pasted_image = paste_result.image_data
        st.image(
            pasted_image, caption="✅ 붙여넣은 이미지 미리보기", width=350
        )
else:
    st.warning(
        "⚠️ `1단계 클립보드 버튼`을 켜려면 GitHub의 `requirements.txt`에 `streamlit-paste-button`을 적어주세요!"
    )

st.write("")
st.markdown("### 📁 2단계: 이미지 파일 직접 올리기 (선택사항)")
uploaded_files = st.file_uploader(
    "PC에 저장된 이미지 파일이 있는 경우 올려주세요",
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


# ---------------------------------------------------------
# 5. 월급 계산 및 AI 분석 로직
# ---------------------------------------------------------
st.write("---")
if st.button("월급 계산하기", type="primary", use_container_width=True):
    images_to_process = []

    if pasted_image is not None:
        images_to_process.append(pasted_image)

    if uploaded_files:
        for f in uploaded_files:
            try:
                images_to_process.append(Image.open(f))
            except Exception:
                pass

    if not images_to_process:
        st.warning("⚠️ 이미지를 붙여넣거나 업로드한 후 계산 버튼을 눌러주세요.")
        st.stop()

    if not api_key:
        st.error(
            "⚠️ API Key가 입력되지 않았습니다. 사이드바에 API 키를 붙여넣어 주세요."
        )
        st.stop()

    try:
        client = genai.Client(api_key=api_key)

        candidate_models = [
            "gemini-2.0-flash",
            "gemini-2.0-flash-exp",
            "gemini-1.5-flash",
            "gemini-1.5-pro",
        ]

        try:
            from_api = [
                m.name.replace("models/", "") for m in client.models.list()
            ]
            for m in from_api:
                if m not in candidate_models and "tts" not in m:
                    candidate_models.append(m)
        except Exception:
            pass

        total_minutes = 0
        total_extracted_income = 0
        total_extracted_expense = 0

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

        with st.spinner("이미지 분석 및 월급 계산 중..."):
            for image in images_to_process:
                response = None
                successful_model = None
                last_error = None

                for model_name in candidate_models:
                    try:
                        res = client.models.generate_content(
                            model=model_name, contents=[image, prompt]
                        )
                        if res and res.text:
                            response = res
                            successful_model = model_name
                            break
                    except Exception as err:
                        last_error = err
                        continue

                if not response:
                    raise Exception(
                        f"이용 가능한 Gemini 모델 연결에 실패했습니다. (마지막 오류: {last_error})"
                    )

                clean_json = (
                    response.text.replace("```json", "")
                    .replace("

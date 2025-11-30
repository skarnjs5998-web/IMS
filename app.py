import streamlit as st
import pandas as pd
from datetime import datetime
import os
from github import Github, GithubException
import io

# --------------------------------------------------------------------------------
# 1. 시스템 설정 및 초기화
# --------------------------------------------------------------------------------
st.set_page_config(page_title="인하대 출판부 재고 관리", layout="wide", page_icon="📚")

# 파일 경로 설정
INVENTORY_FILE = '출판부_재고자산.csv'
HISTORY_FILE = '거래기록.csv'

# GitHub 설정 (secrets.toml에서 로드)
# 로컬 개발 환경에서는 .streamlit/secrets.toml 파일이 필요합니다.
# Streamlit Cloud 배포 시에는 대시보드에서 Secrets에 같은 내용을 입력해야 합니다.
try:
    GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
    REPO_NAME = st.secrets["REPO_NAME"]
    IS_GITHUB_MODE = True
except FileNotFoundError:
    GITHUB_TOKEN = None
    REPO_NAME = None
    IS_GITHUB_MODE = False

st.title("📚 인하대 출판부 재고 관리 시스템")

if IS_GITHUB_MODE:
    st.caption(f"✅ GitHub 연동 모드: `{REPO_NAME}` 저장소와 동기화 중")
else:
    st.caption("⚠️ 로컬 모드: 내 컴퓨터에만 저장됩니다. (.streamlit/secrets.toml 설정 필요)")


# --------------------------------------------------------------------------------
# 2. 데이터 핸들링 함수 (GitHub 양방향 동기화)
# --------------------------------------------------------------------------------
def get_github_repo():
    """GitHub 리포지토리 객체를 가져옵니다."""
    if not GITHUB_TOKEN or not REPO_NAME:
        return None
    g = Github(GITHUB_TOKEN)
    return g.get_repo(REPO_NAME)


def load_data():
    """
    데이터를 로드합니다.
    우선순위: GitHub에서 최신 파일 다운로드 -> 실패 시 로컬 파일 로드 -> 없으면 빈 파일 생성
    """
    df_inv = None
    df_hist = None
    repo = get_github_repo()

    # 1. GitHub에서 데이터 불러오기 시도
    if repo:
        try:
            # 인벤토리 파일
            try:
                contents_inv = repo.get_contents(INVENTORY_FILE)
                df_inv = pd.read_csv(io.StringIO(contents_inv.decoded_content.decode('utf-8')))
            except:
                pass  # 파일이 없으면 패스

            # 거래 기록 파일
            try:
                contents_hist = repo.get_contents(HISTORY_FILE)
                df_hist = pd.read_csv(io.StringIO(contents_hist.decoded_content.decode('utf-8')))
            except:
                pass
        except Exception as e:
            st.error(f"GitHub 연결 오류: {e}")

    # 2. GitHub에 없거나 로드 실패 시, 로컬 확인 또는 초기화
    if df_inv is None:
        if os.path.exists(INVENTORY_FILE):
            df_inv = pd.read_csv(INVENTORY_FILE)
        else:
            # 초기 데이터 생성
            df_inv = pd.DataFrame(columns=['책 이름', '가격', 'ISBN', '현재 수량', '안전 재고'])
            # 예시 데이터
            df_inv.loc[0] = ['인하의 역사', 15000, '979-11-87', 50, 10]
            df_inv.loc[1] = ['파이썬 정복', 25000, '979-11-99', 5, 10]

    if df_hist is None:
        if os.path.exists(HISTORY_FILE):
            df_hist = pd.read_csv(HISTORY_FILE)
        else:
            df_hist = pd.DataFrame(columns=['일시', '거래처', '책 이름', '구분', '수량', '가격'])

    return df_inv, df_hist


def save_data(df_inv, df_hist):
    """
    데이터를 저장합니다.
    로컬 파일 저장 후, GitHub에도 변경 사항을 Push합니다.
    """
    # 1. 로컬 저장 (백업용)
    df_inv.to_csv(INVENTORY_FILE, index=False)
    df_hist.to_csv(HISTORY_FILE, index=False)

    # 2. GitHub 저장 (동기화)
    repo = get_github_repo()
    if repo:
        try:
            # 인벤토리 업데이트
            content_inv = df_inv.to_csv(index=False)
            try:
                contents = repo.get_contents(INVENTORY_FILE)
                repo.update_file(contents.path, "Update Inventory (App)", content_inv, contents.sha)
            except GithubException:  # 파일이 없으면 생성
                repo.create_file(INVENTORY_FILE, "Create Inventory (App)", content_inv)

            # 거래 기록 업데이트
            content_hist = df_hist.to_csv(index=False)
            try:
                contents = repo.get_contents(HISTORY_FILE)
                repo.update_file(contents.path, "Update History (App)", content_hist, contents.sha)
            except GithubException:
                repo.create_file(HISTORY_FILE, "Create History (App)", content_hist)

            st.toast("✅ 데이터가 GitHub에 성공적으로 저장되었습니다!", icon="☁️")
        except Exception as e:
            st.error(f"GitHub 동기화 실패: {e}")
    else:
        st.toast("데이터가 로컬에 저장되었습니다. (GitHub 미연동)", icon="💾")


# 데이터 로드 실행
if 'data_loaded' not in st.session_state:
    st.session_state['df_inventory'], st.session_state['df_history'] = load_data()
    st.session_state['data_loaded'] = True

# 편의를 위해 세션 상태의 데이터를 변수에 할당 (참조)
df_inventory = st.session_state['df_inventory']
df_history = st.session_state['df_history']

# --------------------------------------------------------------------------------
# 3. 사이드바 메뉴
# --------------------------------------------------------------------------------
with st.sidebar:
    st.header("MENU")
    choice = st.radio("이동", ["입출고 입력", "현재 재고", "거래 기록", "알림", "리포트 및 분석"])
    st.divider()
    if st.button("데이터 새로고침 (GitHub 불러오기)"):
        st.session_state['df_inventory'], st.session_state['df_history'] = load_data()
        st.experimental_rerun()

# --------------------------------------------------------------------------------
# 4. 기능 구현
# --------------------------------------------------------------------------------

# [기능 1] 입출고 입력
if choice == "입출고 입력":
    st.subheader("📦 입출고 및 반품 입력")

    with st.form("transaction_form"):
        col1, col2 = st.columns(2)
        with col1:
            tx_type = st.selectbox("거래 유형", ["입고", "출고", "반품"])
            client = st.text_input("거래처 (서점명/인쇄소 등)")

        with col2:
            book_list = df_inventory['책 이름'].tolist()
            selected_book = st.selectbox("책 이름", book_list)
            quantity = st.number_input("수량", min_value=1, value=10)

        submitted = st.form_submit_button("입력 완료")

        if submitted:
            if not client:
                st.warning("거래처를 입력해주세요.")
            else:
                # 데이터 처리 로직
                book_idx = df_inventory[df_inventory['책 이름'] == selected_book].index[0]
                current_qty = df_inventory.at[book_idx, '현재 수량']
                price = df_inventory.at[book_idx, '가격']

                new_qty = current_qty
                if tx_type == "입고":
                    new_qty += quantity
                elif tx_type == "출고":
                    if current_qty < quantity:
                        st.error("❌ 재고가 부족합니다!")
                        st.stop()
                    new_qty -= quantity
                elif tx_type == "반품":
                    new_qty += quantity

                # 업데이트
                df_inventory.at[book_idx, '현재 수량'] = new_qty

                new_record = pd.DataFrame([{
                    '일시': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    '거래처': client,
                    '책 이름': selected_book,
                    '구분': tx_type,
                    '수량': quantity,
                    '가격': price
                }])

                # 최신 기록을 위로 쌓기 위해 concat 순서 조정
                df_history = pd.concat([new_record, df_history], ignore_index=True)

                # 세션 상태 업데이트 및 저장
                st.session_state['df_inventory'] = df_inventory
                st.session_state['df_history'] = df_history
                save_data(df_inventory, df_history)

                st.success(f"처리 완료! '{selected_book}' 재고: {current_qty} -> {new_qty}")

# [기능 2] 현재 재고
elif choice == "현재 재고":
    st.subheader("🔍 현재 재고 현황")

    col1, col2 = st.columns([3, 1])
    with col1:
        search_term = st.text_input("검색 (책 이름 또는 ISBN)", placeholder="검색어를 입력하세요...")

    if search_term:
        mask = df_inventory['책 이름'].astype(str).str.contains(search_term) | df_inventory['ISBN'].astype(
            str).str.contains(search_term)
        result = df_inventory[mask]
    else:
        result = df_inventory

    # 스타일링하여 표시
    st.dataframe(
        result,
        column_config={
            "가격": st.column_config.NumberColumn(format="%d원"),
            "현재 수량": st.column_config.NumberColumn(format="%d권"),
        },
        use_container_width=True,
        hide_index=True
    )

# [기능 3] 거래 기록
elif choice == "거래 기록":
    st.subheader("📜 전체 거래 내역")

    # 최신순 정렬 (일시 기준 내림차순)
    if not df_history.empty:
        df_display = df_history.sort_values(by='일시', ascending=False)
        st.dataframe(
            df_display,
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("아직 거래 기록이 없습니다.")

# [기능 4] 알림
elif choice == "알림":
    st.subheader("🔔 안전 재고 미달 알림")

    alert_list = []
    for idx, row in df_inventory.iterrows():
        if row['현재 수량'] <= row['안전 재고']:
            alert_list.append(row)

    if alert_list:
        for item in alert_list:
            st.error(f"⚠️ **[재고 부족]** '{item['책 이름']}'")
            st.write(f"- 현재 수량: **{item['현재 수량']}권** (안전 재고: {item['안전 재고']}권)")
            st.write(f"- ISBN: {item['ISBN']}")
            st.divider()
    else:
        st.success("✅ 모든 책의 재고가 안전 재고 이상입니다.")

# [기능 5] 리포트 및 분석
elif choice == "리포트 및 분석":
    st.subheader("📊 리포트 및 분석")

    tab1, tab2, tab3 = st.tabs(["📉 월간 판매량", "💰 재고 자산 평가", "🔄 거래처별 반품률"])

    with tab1:
        if not df_history.empty:
            df_hist_copy = df_history.copy()
            df_hist_copy['일시'] = pd.to_datetime(df_hist_copy['일시'])
            df_hist_copy['월'] = df_hist_copy['일시'].dt.strftime('%Y-%m')

            # 출고(판매) 데이터만
            sales_df = df_hist_copy[df_hist_copy['구분'] == '출고']

            if not sales_df.empty:
                monthly_sales = sales_df.pivot_table(index='월', columns='책 이름', values='수량', aggfunc='sum',
                                                     fill_value=0)
                st.bar_chart(monthly_sales)
                st.write("상세 데이터:")
                st.dataframe(monthly_sales)
            else:
                st.info("판매(출고) 데이터가 없습니다.")
        else:
            st.info("거래 데이터가 없습니다.")

    with tab2:
        df_inv_copy = df_inventory.copy()
        df_inv_copy['총액'] = df_inv_copy['현재 수량'] * df_inv_copy['가격']
        total_asset = df_inv_copy['총액'].sum()

        st.metric("총 재고 자산", f"{total_asset:,.0f} 원")

        st.dataframe(
            df_inv_copy[['책 이름', '현재 수량', '가격', '총액']],
            column_config={
                "가격": st.column_config.NumberColumn(format="%d원"),
                "총액": st.column_config.NumberColumn(format="%d원"),
            },
            use_container_width=True
        )

    with tab3:
        if not df_history.empty:
            # 거래처별 집계
            df_client = df_history.groupby(['거래처', '구분'])['수량'].sum().unstack(fill_value=0)

            if '출고' in df_client.columns:
                if '반품' not in df_client.columns:
                    df_client['반품'] = 0

                # 반품률 계산
                df_client['반품률(%)'] = df_client.apply(
                    lambda x: (x['반품'] / x['출고'] * 100) if x['출고'] > 0 else 0, axis=1
                )

                st.dataframe(
                    df_client[['출고', '반품', '반품률(%)']].style.format({'반품률(%)': "{:.2f}%"}),
                    use_container_width=True
                )
            else:
                st.info("출고 데이터가 부족하여 반품률을 계산할 수 없습니다.")
        else:
            st.info("거래 데이터가 없습니다.")
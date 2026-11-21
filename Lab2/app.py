import streamlit as st
import sys

st.set_page_config(
    page_title='Aplikacja testowa',
    layout='wide'
)



pages = [
    st.Page(
        f'views/page{i}.py',
        title=f'Strona {i}',
        url_path=f'strona-{i}'
    )
    for i in range(1,3)
]

navigation = st.navigation(pages, position='sidebar')
navigation.run()
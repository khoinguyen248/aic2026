import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { ConfigProvider, App as AntdApp } from 'antd'
import './index.css'
import App from './App.jsx'
import { aicTheme } from './theme'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <ConfigProvider theme={aicTheme}>
      <AntdApp>
        <App />
      </AntdApp>
    </ConfigProvider>
  </StrictMode>,
)

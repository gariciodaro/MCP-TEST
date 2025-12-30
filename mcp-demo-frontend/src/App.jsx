import { useState, useEffect, useRef } from 'react'
import ReactMarkdown from 'react-markdown'
import './App.css'

const API_BASE = 'http://localhost:8000'

function App() {
  const [connected, setConnected] = useState(false)
  const [serverPath, setServerPath] = useState('F:\\my-code\\MCP-TEST\\weather-mcp-server\\weather.py')
  const [tools, setTools] = useState([])
  const [resources, setResources] = useState([])
  const [prompts, setPrompts] = useState([])
  const [messages, setMessages] = useState([])
  const [inputMessage, setInputMessage] = useState('')
  const [loading, setLoading] = useState(false)
  const [activeTab, setActiveTab] = useState('chat')
  const [selectedResource, setSelectedResource] = useState(null)
  const [resourceContent, setResourceContent] = useState(null)
  const [loadingResource, setLoadingResource] = useState(false)
  const [selectedPrompt, setSelectedPrompt] = useState(null)
  const [promptArgs, setPromptArgs] = useState({})
  const [loadingPrompt, setLoadingPrompt] = useState(false)
  const [promptPreview, setPromptPreview] = useState(null)
  const messagesEndRef = useRef(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  useEffect(() => {
    checkStatus()
  }, [])

  const checkStatus = async () => {
    try {
      const res = await fetch(`${API_BASE}/status`)
      const data = await res.json()
      setConnected(data.connected)
      if (data.connected) {
        setTools(data.tools || [])
        setResources(data.resources || [])
        setPrompts(data.prompts || [])
      }
    } catch (err) {
      console.error('Failed to check status:', err)
    }
  }

  const connect = async () => {
    setLoading(true)
    try {
      const res = await fetch(`${API_BASE}/connect`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ server_path: serverPath })
      })
      const data = await res.json()
      if (res.ok) {
        setConnected(true)
        setTools(data.tools || [])
        setResources(data.resources || [])
        setPrompts(data.prompts || [])
        setMessages([{ role: 'system', content: `Connected to MCP server. Available tools: ${data.tools.map(t => t.name).join(', ')}` }])
      } else {
        alert(`Failed to connect: ${data.detail}`)
      }
    } catch (err) {
      alert(`Connection error: ${err.message}`)
    }
    setLoading(false)
  }

  const disconnect = async () => {
    setLoading(true)
    try {
      await fetch(`${API_BASE}/disconnect`, { method: 'POST' })
      setConnected(false)
      setTools([])
      setResources([])
      setPrompts([])
      setMessages([])
    } catch (err) {
      console.error('Disconnect error:', err)
    }
    setLoading(false)
  }

  const sendMessage = async () => {
    if (!inputMessage.trim() || !connected) return

    const userMessage = { role: 'user', content: inputMessage }
    setMessages(prev => [...prev, userMessage])
    setInputMessage('')
    setLoading(true)

    try {
      const res = await fetch(`${API_BASE}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: inputMessage })
      })
      const data = await res.json()
      
      if (res.ok) {
        // Add tool calls if any
        if (data.tool_calls && data.tool_calls.length > 0) {
          for (const tc of data.tool_calls) {
            setMessages(prev => [...prev, {
              role: 'tool',
              name: tc.name,
              arguments: tc.arguments,
              result: tc.result
            }])
          }
        }
        // Add assistant response
        setMessages(prev => [...prev, { role: 'assistant', content: data.response }])
      } else {
        setMessages(prev => [...prev, { role: 'error', content: data.detail }])
      }
    } catch (err) {
      setMessages(prev => [...prev, { role: 'error', content: err.message }])
    }
    setLoading(false)
  }

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  const readResource = async (uri) => {
    setLoadingResource(true)
    setSelectedResource(uri)
    try {
      const res = await fetch(`${API_BASE}/resources/read`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ uri })
      })
      const data = await res.json()
      if (res.ok) {
        setResourceContent(data.content || data.error)
      } else {
        setResourceContent(`Error: ${data.detail}`)
      }
    } catch (err) {
      setResourceContent(`Error: ${err.message}`)
    }
    setLoadingResource(false)
  }

  const closeResourceModal = () => {
    setSelectedResource(null)
    setResourceContent(null)
  }

  const selectPrompt = (prompt) => {
    setSelectedPrompt(prompt)
    // Initialize arguments with empty strings
    const args = {}
    if (prompt.arguments) {
      prompt.arguments.forEach(arg => {
        args[arg.name] = ''
      })
    }
    setPromptArgs(args)
  }

  const closePromptModal = () => {
    setSelectedPrompt(null)
    setPromptArgs({})
    setPromptPreview(null)
  }

  const updatePromptArg = (name, value) => {
    setPromptArgs(prev => ({ ...prev, [name]: value }))
    setPromptPreview(null) // Clear preview when args change
  }

  const previewPrompt = async () => {
    if (!selectedPrompt) return
    
    setLoadingPrompt(true)
    try {
      const res = await fetch(`${API_BASE}/prompts/get`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          name: selectedPrompt.name, 
          arguments: promptArgs 
        })
      })
      const data = await res.json()
      
      if (res.ok && data.messages && data.messages.length > 0) {
        const userMsg = data.messages.find(m => m.role === 'user')
        if (userMsg) {
          setPromptPreview(userMsg.content)
        }
      } else {
        alert(`Failed to get prompt: ${data.detail || 'Unknown error'}`)
      }
    } catch (err) {
      alert(`Error: ${err.message}`)
    }
    setLoadingPrompt(false)
  }

  const usePrompt = async () => {
    if (promptPreview) {
      // Use existing preview
      setInputMessage(promptPreview)
      setActiveTab('chat')
      closePromptModal()
      return
    }
    
    // No preview yet, fetch and use directly
    setLoadingPrompt(true)
    try {
      const res = await fetch(`${API_BASE}/prompts/get`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          name: selectedPrompt.name, 
          arguments: promptArgs 
        })
      })
      const data = await res.json()
      
      if (res.ok && data.messages && data.messages.length > 0) {
        const userMsg = data.messages.find(m => m.role === 'user')
        if (userMsg) {
          setInputMessage(userMsg.content)
          setActiveTab('chat')
          closePromptModal()
        }
      } else {
        alert(`Failed to get prompt: ${data.detail || 'Unknown error'}`)
      }
    } catch (err) {
      alert(`Error: ${err.message}`)
    }
    setLoadingPrompt(false)
  }

  return (
    <div className="app">
      {/* Header */}
      <header className="header">
        <div className="header-left">
          <h1>🔌 MCP Demo</h1>
          <span className={`status-badge ${connected ? 'connected' : 'disconnected'}`}>
            {connected ? '● Connected' : '○ Disconnected'}
          </span>
        </div>
        <div className="header-right">
          <input
            type="text"
            value={serverPath}
            onChange={(e) => setServerPath(e.target.value)}
            placeholder="Path to MCP server script"
            className="server-input"
            disabled={connected}
          />
          <button 
            onClick={connected ? disconnect : connect}
            disabled={loading}
            className={`btn ${connected ? 'btn-danger' : 'btn-primary'}`}
          >
            {loading ? '...' : (connected ? 'Disconnect' : 'Connect')}
          </button>
        </div>
      </header>

      {/* Main Content */}
      <div className="main-content">
        {/* Sidebar */}
        <aside className="sidebar">
          <nav className="tabs">
            <button 
              className={`tab ${activeTab === 'chat' ? 'active' : ''}`}
              onClick={() => setActiveTab('chat')}
            >
              💬 Chat
            </button>
            <button 
              className={`tab ${activeTab === 'tools' ? 'active' : ''}`}
              onClick={() => setActiveTab('tools')}
            >
              🔧 Tools ({tools.length})
            </button>
            <button 
              className={`tab ${activeTab === 'resources' ? 'active' : ''}`}
              onClick={() => setActiveTab('resources')}
            >
              📦 Resources ({resources.length})
            </button>
            <button 
              className={`tab ${activeTab === 'prompts' ? 'active' : ''}`}
              onClick={() => setActiveTab('prompts')}
            >
              📝 Prompts ({prompts.length})
            </button>
          </nav>

          {/* Sidebar Content */}
          <div className="sidebar-content">
            {activeTab === 'tools' && (
              <div className="tools-list">
                <h3>Available Tools</h3>
                {tools.length === 0 ? (
                  <p className="empty-state">No tools available. Connect to a server first.</p>
                ) : (
                  tools.map((tool, idx) => (
                    <div key={idx} className="tool-card">
                      <div className="tool-name">{tool.name}</div>
                      <div className="tool-description">{tool.description}</div>
                      {tool.input_schema?.properties && (
                        <div className="tool-params">
                          <strong>Parameters:</strong>
                          <ul>
                            {Object.entries(tool.input_schema.properties).map(([name, schema]) => (
                              <li key={name}>
                                <code>{name}</code>: {schema.type}
                                {schema.description && ` - ${schema.description}`}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  ))
                )}
              </div>
            )}

            {activeTab === 'resources' && (
              <div className="resources-list">
                <h3>Available Resources</h3>
                <p className="resources-hint">Click a resource to read its content</p>
                {resources.length === 0 ? (
                  <p className="empty-state">No resources available.</p>
                ) : (
                  resources.map((res, idx) => (
                    <div 
                      key={idx} 
                      className="resource-card clickable"
                      onClick={() => readResource(res.uri)}
                    >
                      <div className="resource-uri">{res.uri}</div>
                      <div className="resource-name">{res.name}</div>
                      {res.description && <div className="resource-description">{res.description}</div>}
                      <div className="resource-action">📖 Click to read</div>
                    </div>
                  ))
                )}
              </div>
            )}

            {activeTab === 'prompts' && (
              <div className="prompts-list">
                <h3>Available Prompts</h3>
                <p className="prompts-hint">Click a prompt to use it</p>
                {prompts.length === 0 ? (
                  <p className="empty-state">No prompts available.</p>
                ) : (
                  prompts.map((prompt, idx) => (
                    <div 
                      key={idx} 
                      className="prompt-card clickable"
                      onClick={() => selectPrompt(prompt)}
                    >
                      <div className="prompt-name">{prompt.name}</div>
                      {prompt.description && <div className="prompt-description">{prompt.description}</div>}
                      {prompt.arguments && prompt.arguments.length > 0 && (
                        <div className="prompt-args-preview">
                          <strong>Arguments:</strong> {prompt.arguments.map(a => a.name).join(', ')}
                        </div>
                      )}
                      <div className="prompt-action">📝 Click to use</div>
                    </div>
                  ))
                )}
              </div>
            )}

            {activeTab === 'chat' && (
              <div className="chat-info">
                <h3>MCP Chat Demo</h3>
                <p>Ask questions about weather to see MCP tools in action!</p>
                <div className="example-queries">
                  <h4>Try asking:</h4>
                  <ul>
                    <li>"What's the weather forecast for latitude 40.7, longitude -74.0?"</li>
                    <li>"Are there any weather alerts in CA?"</li>
                    <li>"Get the forecast for NYC (40.7128, -74.0060)"</li>
                  </ul>
                </div>
              </div>
            )}
          </div>
        </aside>

        {/* Chat Area */}
        <main className="chat-area">
          <div className="messages">
            {messages.map((msg, idx) => (
              <div key={idx} className={`message ${msg.role}`}>
                {msg.role === 'user' && (
                  <div className="message-content user-message">
                    <span className="message-icon">👤</span>
                    <div className="message-text">{msg.content}</div>
                  </div>
                )}
                {msg.role === 'assistant' && (
                  <div className="message-content assistant-message">
                    <span className="message-icon">🤖</span>
                    <div className="message-text markdown-content">
                      <ReactMarkdown>{msg.content}</ReactMarkdown>
                    </div>
                  </div>
                )}
                {msg.role === 'tool' && (
                  <div className="message-content tool-message">
                    <span className="message-icon">🔧</span>
                    <div className="tool-call-info">
                      <div className="tool-call-header">
                        Tool Call: <code>{msg.name}</code>
                      </div>
                      <div className="tool-call-args">
                        <strong>Arguments:</strong>
                        <pre>{JSON.stringify(msg.arguments, null, 2)}</pre>
                      </div>
                      <div className="tool-call-result">
                        <strong>Result:</strong>
                        <pre>{msg.result}</pre>
                      </div>
                    </div>
                  </div>
                )}
                {msg.role === 'system' && (
                  <div className="message-content system-message">
                    <span className="message-icon">ℹ️</span>
                    <div className="message-text">{msg.content}</div>
                  </div>
                )}
                {msg.role === 'error' && (
                  <div className="message-content error-message">
                    <span className="message-icon">❌</span>
                    <div className="message-text">{msg.content}</div>
                  </div>
                )}
              </div>
            ))}
            {loading && (
              <div className="message loading">
                <div className="message-content">
                  <span className="loading-dots">⏳ Processing...</span>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Input Area */}
          <div className="input-area">
            <textarea
              value={inputMessage}
              onChange={(e) => setInputMessage(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder={connected ? "Type a message..." : "Connect to an MCP server first"}
              disabled={!connected || loading}
              rows={2}
            />
            <button 
              onClick={sendMessage} 
              disabled={!connected || loading || !inputMessage.trim()}
              className="btn btn-primary send-btn"
            >
              Send
            </button>
          </div>
        </main>
      </div>

      {/* Resource Modal */}
      {selectedResource && (
        <div className="modal-overlay" onClick={closeResourceModal}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>📦 Resource Content</h2>
              <button className="modal-close" onClick={closeResourceModal}>✕</button>
            </div>
            <div className="modal-uri">{selectedResource}</div>
            <div className="modal-content">
              {loadingResource ? (
                <div className="loading-resource">Loading resource...</div>
              ) : (
                <pre>{resourceContent}</pre>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Prompt Modal */}
      {selectedPrompt && (
        <div className="modal-overlay" onClick={closePromptModal}>
          <div className="modal prompt-modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>📝 Use Prompt</h2>
              <button className="modal-close" onClick={closePromptModal}>✕</button>
            </div>
            <div className="prompt-modal-name">{selectedPrompt.name}</div>
            {selectedPrompt.description && (
              <div className="prompt-modal-description">{selectedPrompt.description}</div>
            )}
            
            {selectedPrompt.arguments && selectedPrompt.arguments.length > 0 ? (
              <div className="prompt-args-form">
                <h4>Fill in the arguments:</h4>
                {selectedPrompt.arguments.map((arg, idx) => (
                  <div key={idx} className="prompt-arg-field">
                    <label htmlFor={`arg-${arg.name}`}>
                      {arg.name}
                      {arg.required && <span className="required">*</span>}
                    </label>
                    {arg.description && (
                      <span className="arg-description">{arg.description}</span>
                    )}
                    <input
                      id={`arg-${arg.name}`}
                      type="text"
                      value={promptArgs[arg.name] || ''}
                      onChange={(e) => updatePromptArg(arg.name, e.target.value)}
                      placeholder={`Enter ${arg.name}...`}
                    />
                  </div>
                ))}
              </div>
            ) : (
              <p className="no-args-message">This prompt has no arguments.</p>
            )}

            {promptPreview && (
              <div className="prompt-preview">
                <h4>Preview:</h4>
                <div className="prompt-preview-content markdown-content">
                  <ReactMarkdown>{promptPreview}</ReactMarkdown>
                </div>
              </div>
            )}
            
            <div className="prompt-modal-actions">
              <button 
                className="btn btn-secondary" 
                onClick={closePromptModal}
              >
                Cancel
              </button>
              <button 
                className="btn btn-outline" 
                onClick={previewPrompt}
                disabled={loadingPrompt}
              >
                {loadingPrompt ? 'Loading...' : '👁️ Preview'}
              </button>
              <button 
                className="btn btn-primary" 
                onClick={usePrompt}
                disabled={loadingPrompt}
              >
                {promptPreview ? 'Use Prompt' : 'Use Prompt'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default App

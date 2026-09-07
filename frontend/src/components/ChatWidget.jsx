import { useState, useEffect, useRef } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  MessageSquare,
  Sparkles,
  Send,
  X,
  RotateCcw,
  Star,
  ExternalLink,
  ShoppingBag,
  Package,
  Plus,
  Bot,
  User,
  ChevronDown,
} from 'lucide-react'
import client from '../api/client'
import { useCart } from '../context/CartContext'
import './ChatWidget.css'

const STORAGE_KEY = 'shopwave_chat_history'

const INITIAL_MESSAGE = {
  id: 'welcome',
  role: 'assistant',
  content:
    "👋 Hello! I'm your **ShopWave AI Assistant**.\n\nI can help you discover items in our catalog, track orders, or answer questions about shipping and store policies. How can I assist you today?",
  products: [],
}

const SUGGESTIONS = [
  { label: '🎧 Tech under $300', prompt: 'Can you recommend top tech or headphones under $300?' },
  { label: '📦 Track order #1001', prompt: 'Can you check the delivery status of order #1001?' },
  { label: '✨ Daily essentials', prompt: 'What are your most popular daily essentials?' },
  { label: '🚚 Shipping & returns', prompt: 'What is your shipping time and return policy?' },
]

export default function ChatWidget() {
  const { addToCart } = useCart()
  const navigate = useNavigate()

  const [isOpen, setIsOpen] = useState(false)
  const [messages, setMessages] = useState(() => {
    try {
      const saved = sessionStorage.getItem(STORAGE_KEY)
      if (saved) {
        const parsed = JSON.parse(saved)
        if (Array.isArray(parsed) && parsed.length > 0) return parsed
      }
    } catch {
      // ignore
    }
    return [INITIAL_MESSAGE]
  })
  const [inputValue, setInputValue] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [hasUnread, setHasUnread] = useState(false)

  const messagesEndRef = useRef(null)
  const inputRef = useRef(null)

  // Persist messages to sessionStorage
  useEffect(() => {
    try {
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify(messages))
    } catch {
      // ignore
    }
  }, [messages])

  // Scroll to bottom when new messages arrive or loading state changes
  useEffect(() => {
    if (isOpen) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
  }, [messages, isLoading, isOpen])

  // Auto-focus input on open
  useEffect(() => {
    if (isOpen) {
      setHasUnread(false)
      setTimeout(() => inputRef.current?.focus(), 150)
    }
  }, [isOpen])

  // Allow external triggers (such as Navbar button) to open chat
  useEffect(() => {
    const handleOpen = () => setIsOpen(true)
    window.addEventListener('open-shopwave-chat', handleOpen)
    return () => window.removeEventListener('open-shopwave-chat', handleOpen)
  }, [])

  const handleSendMessage = async (textToSend) => {
    const query = (textToSend || inputValue).trim()
    if (!query || isLoading) return

    const userMsgId = Date.now().toString()
    const userMessage = {
      id: userMsgId,
      role: 'user',
      content: query,
    }

    // Append user message immediately
    const updatedMessages = [...messages, userMessage]
    setMessages(updatedMessages)
    setInputValue('')
    setIsLoading(true)

    // Format history for backend API (excluding welcome greeting)
    const historyPayload = updatedMessages
      .filter((m) => m.id !== 'welcome')
      .map((m) => ({
        role: m.role,
        content: m.content,
      }))

    try {
      const response = await client.post('/chat', {
        message: query,
        history: historyPayload.slice(-8), // Send last 8 turns
      })

      const botMessage = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: response.data.reply || "I've processed your request.",
        products: response.data.products || [],
        toolCalls: response.data.tool_calls || [],
      }

      setMessages((prev) => [...prev, botMessage])

      if (!isOpen) {
        setHasUnread(true)
      }
    } catch (err) {
      console.error('Chat error:', err)
      const errorMessage = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content:
          "I'm sorry, I ran into a connection issue. Please try again in a moment or browse our products directly from the navigation bar.",
        products: [],
      }
      setMessages((prev) => [...prev, errorMessage])
    } finally {
      setIsLoading(false)
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSendMessage()
    }
  }

  const handleResetChat = () => {
    setMessages([INITIAL_MESSAGE])
    try {
      sessionStorage.removeItem(STORAGE_KEY)
    } catch {}
  }

  const handleAddProduct = async (e, productId) => {
    e.stopPropagation()
    e.preventDefault()
    await addToCart(productId, 1)
  }

  // Format basic markdown styling (bold, lists, line breaks)
  const renderFormattedContent = (content) => {
    if (!content) return null

    const lines = content.split('\n')
    return (
      <div className="chat-markdown">
        {lines.map((line, idx) => {
          if (!line.trim()) return <div key={idx} className="chat-empty-line" />

          // Parse markdown links [text](url) and bold **text**
          const renderLineParts = (text) => {
            // Match markdown links: [text](url)
            const linkRegex = /\[([^\]]+)\]\(([^)]+)\)/g
            const parts = []
            let lastIndex = 0
            let match

            while ((match = linkRegex.exec(text)) !== null) {
              if (match.index > lastIndex) {
                parts.push(renderBoldText(text.substring(lastIndex, match.index)))
              }
              const linkText = match[1]
              const linkUrl = match[2]
              parts.push(
                <a
                  key={`link-${match.index}`}
                  href={linkUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="chat-inline-link"
                >
                  {linkText}
                </a>
              )
              lastIndex = match.index + match[0].length
            }

            if (lastIndex < text.length) {
              parts.push(renderBoldText(text.substring(lastIndex)))
            }

            return parts.length > 0 ? parts : renderBoldText(text)
          }

          const renderBoldText = (str) => {
            const boldRegex = /\*\*([^*]+)\*\*/g
            const chunks = []
            let lastIdx = 0
            let m

            while ((m = boldRegex.exec(str)) !== null) {
              if (m.index > lastIdx) {
                chunks.push(str.substring(lastIdx, m.index))
              }
              chunks.push(<strong key={`bold-${m.index}`}>{m[1]}</strong>)
              lastIdx = m.index + m[0].length
            }

            if (lastIdx < str.length) {
              chunks.push(str.substring(lastIdx))
            }
            return chunks
          }

          if (line.startsWith('* ') || line.startsWith('- ')) {
            return (
              <div key={idx} className="chat-list-item">
                <span className="chat-bullet">•</span>
                <span>{renderLineParts(line.substring(2))}</span>
              </div>
            )
          }

          return <p key={idx} className="chat-text-p">{renderLineParts(line)}</p>
        })}
      </div>
    )
  }

  return (
    <div className="chat-widget-root">
      {/* ── Floating Launcher Button ───────────────────────────────── */}
      {!isOpen && (
        <button
          className="chat-launcher-btn"
          id="shopwave-chat-launcher"
          onClick={() => setIsOpen(true)}
          aria-label="Open AI Shopping Assistant"
        >
          <div className="launcher-icon-wrap">
            <Sparkles className="launcher-sparkle-icon" size={18} />
            <MessageSquare size={24} />
          </div>
          <span className="launcher-label">Ask ShopWave AI</span>
          {hasUnread && <span className="launcher-unread-dot" />}
        </button>
      )}

      {/* ── Chat Window / Drawer ───────────────────────────────────── */}
      {isOpen && (
        <div className="chat-drawer" id="shopwave-chat-drawer">
          {/* Drawer Header */}
          <div className="chat-header">
            <div className="chat-header-info">
              <div className="chat-avatar-ai">
                <Bot size={18} />
                <span className="chat-online-indicator" />
              </div>
              <div>
                <div className="chat-title-row">
                  <h3 className="chat-title">ShopWave AI</h3>
                  <span className="chat-badge-pill">Assistant</span>
                </div>
                <p className="chat-subtitle">Real-time products & live order tracking</p>
              </div>
            </div>

            <div className="chat-header-actions">
              <button
                className="chat-icon-btn"
                title="Clear Conversation"
                onClick={handleResetChat}
                aria-label="Clear chat"
              >
                <RotateCcw size={16} />
              </button>
              <button
                className="chat-icon-btn"
                title="Close chat"
                onClick={() => setIsOpen(false)}
                aria-label="Close chat"
              >
                <ChevronDown size={18} />
              </button>
            </div>
          </div>

          {/* Drawer Body / Messages */}
          <div className="chat-body">
            {messages.map((msg) => (
              <div
                key={msg.id}
                className={`chat-message-row ${msg.role === 'user' ? 'user-row' : 'bot-row'}`}
              >
                {msg.role === 'assistant' && (
                  <div className="msg-avatar bot-avatar">
                    <Bot size={14} />
                  </div>
                )}

                <div className={`chat-bubble ${msg.role === 'user' ? 'user-bubble' : 'bot-bubble'}`}>
                  {renderFormattedContent(msg.content)}

                  {/* Product Recommendation Cards Carousel / Grid */}
                  {msg.products && msg.products.length > 0 && (
                    <div className="chat-products-container">
                      <div className="chat-products-header">
                        <ShoppingBag size={14} />
                        <span>Recommended Products ({msg.products.length})</span>
                      </div>
                      <div className="chat-products-grid">
                        {msg.products.map((product) => (
                          <div
                            key={product.id}
                            className="chat-product-card"
                            onClick={() => {
                              navigate(`/products/${product.id}`)
                              setIsOpen(false)
                            }}
                          >
                            <div className="card-thumb-wrap">
                              <img
                                src={product.image_url || 'https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=300'}
                                alt={product.name}
                                className="card-thumb-img"
                                loading="lazy"
                              />
                              <span className="card-category-tag">{product.category}</span>
                            </div>
                            <div className="card-info">
                              <h4 className="card-product-name" title={product.name}>
                                {product.name}
                              </h4>
                              <div className="card-meta-row">
                                <span className="card-price">${product.price.toFixed(2)}</span>
                                <span className="card-rating">
                                  <Star size={12} fill="#f59e0b" color="#f59e0b" />
                                  {product.rating}
                                </span>
                              </div>
                              <div className="card-actions-row">
                                <Link
                                  to={`/products/${product.id}`}
                                  className="card-view-btn"
                                  onClick={(e) => {
                                    e.stopPropagation()
                                    setIsOpen(false)
                                  }}
                                >
                                  View Details <ExternalLink size={11} />
                                </Link>
                                <button
                                  type="button"
                                  className="card-add-btn"
                                  title="Add to Cart"
                                  onClick={(e) => handleAddProduct(e, product.id)}
                                >
                                  <Plus size={14} /> Add
                                </button>
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>

                {msg.role === 'user' && (
                  <div className="msg-avatar user-avatar">
                    <User size={14} />
                  </div>
                )}
              </div>
            ))}

            {/* Typing Indicator */}
            {isLoading && (
              <div className="chat-message-row bot-row">
                <div className="msg-avatar bot-avatar">
                  <Bot size={14} />
                </div>
                <div className="chat-bubble bot-bubble typing-bubble">
                  <div className="typing-dots">
                    <span className="dot" />
                    <span className="dot" />
                    <span className="dot" />
                  </div>
                  <span className="typing-label">ShopWave AI is searching catalog...</span>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Quick Suggestion Chips */}
          {messages.length <= 2 && (
            <div className="chat-suggestions-wrap">
              <div className="suggestions-header">
                <Sparkles size={12} />
                <span>Suggested prompts</span>
              </div>
              <div className="suggestions-list">
                {SUGGESTIONS.map((s, idx) => (
                  <button
                    key={idx}
                    className="suggestion-chip"
                    onClick={() => handleSendMessage(s.prompt)}
                    disabled={isLoading}
                  >
                    {s.label}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Drawer Footer / Input Form */}
          <div className="chat-footer">
            <form
              className="chat-input-form"
              onSubmit={(e) => {
                e.preventDefault()
                handleSendMessage()
              }}
            >
              <input
                ref={inputRef}
                type="text"
                className="chat-input"
                id="shopwave-chat-input"
                placeholder="Ask about products, orders, shipping..."
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyDown={handleKeyDown}
                disabled={isLoading}
              />
              <button
                type="submit"
                className="chat-send-btn"
                id="shopwave-chat-send-btn"
                disabled={!inputValue.trim() || isLoading}
                aria-label="Send message"
              >
                <Send size={16} />
              </button>
            </form>
            <div className="chat-powered-by">
              <span>Powered by Google Gemini Tool Calling</span>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

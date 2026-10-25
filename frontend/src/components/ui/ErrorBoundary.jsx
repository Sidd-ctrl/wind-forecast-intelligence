import { Component } from 'react'

export class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { error: null }
  }

  static getDerivedStateFromError(error) {
    return { error }
  }

  render() {
    if (this.state.error) {
      return (
        <div style={{ padding: 32, maxWidth: 640, margin: '0 auto' }}>
          <div className="state-block state-block--error" role="alert">
            <p className="state-block__title">Interface error</p>
            <p className="state-block__text">
              AERON encountered an unexpected interface error. The backend data is unaffected. Reload the page to
              continue.
            </p>
            <button type="button" className="btn" onClick={() => window.location.reload()}>
              Reload interface
            </button>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}

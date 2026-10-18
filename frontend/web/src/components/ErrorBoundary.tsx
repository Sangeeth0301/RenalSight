import { Component, type ReactNode } from "react";
import { withTranslation, type WithTranslation } from "react-i18next";

class Boundary extends Component<WithTranslation & { children: ReactNode }, { err: Error | null }> {
  state = { err: null as Error | null };
  static getDerivedStateFromError(err: Error) { return { err }; }
  render() {
    if (!this.state.err) return this.props.children;
    const { t } = this.props;
    return (
      <div className="grid h-full place-items-center p-6">
        <div className="card max-w-md p-6 text-center">
          <p className="text-lg font-semibold">{t("errors.generic")}</p>
          <button className="btn-primary mt-4" onClick={() => { this.setState({ err: null }); location.reload(); }}>{t("app.retry")}</button>
        </div>
      </div>
    );
  }
}
export const ErrorBoundary = withTranslation()(Boundary);

import { useState } from "react";

export default function LoginView({ onLogin }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const submit = async (event) => {
    event.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      await onLogin(username, password);
    } catch (requestError) {
      setError(requestError.message || "Login failed. Please try again.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <main className="min-h-screen flex items-center justify-center bg-[#f8fafc] p-4 text-slate-800">
      <div className="w-full max-w-md space-y-4">
        <div className="text-center">
          <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-[#14232e] text-sm font-bold text-white">
            DSS
          </div>
          <p className="text-sm font-semibold text-slate-700">Olist DSS</p>
        </div>
        <section className="panel space-y-6 p-8">
          <div>
            <h1 className="text-xl font-bold text-slate-900">
              Đăng nhập hệ thống
            </h1>
            <p className="mt-1 text-xs text-slate-500">
              Nhập thông tin xác thực để truy cập bảng điều khiển DSS.
            </p>
          </div>
          <form onSubmit={submit} className="space-y-4">
            <div>
              <label
                htmlFor="login-username"
                className="mb-1 block text-xs font-medium text-slate-600"
              >
                Tài khoản / Email
              </label>
              <input
                id="login-username"
                name="username"
                type="text"
                required
                autoComplete="username"
                placeholder="admin"
                className="sel w-full"
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                disabled={submitting}
              />
            </div>
            <div>
              <label
                htmlFor="login-password"
                className="mb-1 block text-xs font-medium text-slate-600"
              >
                Mật khẩu
              </label>
              <input
                id="login-password"
                name="password"
                type="password"
                required
                autoComplete="current-password"
                placeholder="••••••••"
                className="sel w-full"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                disabled={submitting}
              />
            </div>
            {error && (
              <p className="rounded bg-red-50 px-3 py-2 text-sm text-red-800" role="alert">
                {error}
              </p>
            )}
            <button
              type="submit"
              className="btn btn-main w-full py-2"
              disabled={submitting}
              aria-busy={submitting}
            >
              {submitting ? "Đang xác thực..." : "Truy cập Dashboard"}
            </button>
          </form>
          <div className="border-t border-slate-100 pt-4 text-center text-[11px] text-slate-500">
            Phiên đăng nhập được quản lý an toàn bởi máy chủ.
          </div>
        </section>
      </div>
    </main>
  );
}

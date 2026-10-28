import { render, screen } from "@testing-library/react"
import { BrowserRouter } from "react-router-dom"
import { describe, expect, it, vi } from "vitest"

import { LoginPage } from "@/pages/LoginPage"

vi.mock("@/lib/AuthContext", () => ({
  useAuth: () => ({ login: vi.fn(), user: null, isLoading: false }),
}))

describe("LoginPage", () => {
  it("renders the sign-in form", () => {
    render(
      <BrowserRouter>
        <LoginPage />
      </BrowserRouter>,
    )

    expect(screen.getByRole("heading", { name: /sign in to envforge/i })).toBeInTheDocument()
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /sign in/i })).toBeInTheDocument()
  })
})

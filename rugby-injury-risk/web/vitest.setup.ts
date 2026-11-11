import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// globals désactivés : le nettoyage du DOM entre tests doit être explicite.
afterEach(() => {
  cleanup();
});

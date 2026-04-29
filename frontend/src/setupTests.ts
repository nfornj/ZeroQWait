import "@testing-library/jest-dom";

jest.mock("axios", () => {
  const mockAxios = {
    create: jest.fn(),
    get: jest.fn(),
    post: jest.fn(),
    put: jest.fn(),
    patch: jest.fn(),
    delete: jest.fn(),
    defaults: { headers: { common: {} } },
    interceptors: {
      request: {
        use: jest.fn(),
        eject: jest.fn(),
      },
      response: {
        use: jest.fn(),
        eject: jest.fn(),
      },
    },
  };

  mockAxios.create.mockReturnValue(mockAxios);

  return {
    __esModule: true,
    default: mockAxios,
    ...mockAxios,
  };
});
import request from "@/api/index"

export function registerAPI(payload) {
  return request({
    url: "auth/register",
    method: "POST",
    data: payload,
  })
}

export function loginAPI(payload) {
  return request({
    url: "auth/login",
    method: "POST",
    data: payload,
  })
}

export function getCurrentUserAPI() {
  return request({
    url: "auth/me",
    method: "GET",
  })
}

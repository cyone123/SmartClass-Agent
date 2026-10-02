import request from "@/api/index"

export function getPlanAndSessionListAPI() {
    return request({
        url: 'plan',
        method: 'GET'
    })
}

export function addPlanAPI(plan) {
    return request({
        url: 'plan',
        method: 'PUT',
        data: plan
    })
}

export function deletePlanAPI(plan_id) {
    return request({
        url: `plan/${plan_id}`,
        method: 'DELETE'
    })
}

export function updatePlanAPI(plan) {
    return request({
        url: 'plan',
        method: 'POST',
        data: plan
    })
}

export function updateSessionAPI(session) {
    return request({
        url: `session`,
        method: 'POST',
        data: session
    })
}

export function deleteSessionAPI(session_id) {
    return request({
        url: `session/${session_id}`,
        method: 'DELETE'
    })
}

export function addSessionAPI(session) {
    return request({
        url: 'session',
        method: 'PUT',
        data: session
    })
}

export function getMessageHistry(thread_id) {
    return request({
        url: `session/${thread_id}`,
        method: 'GET'
    })
}
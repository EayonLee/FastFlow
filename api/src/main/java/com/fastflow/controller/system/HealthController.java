package com.fastflow.controller.system;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.time.Instant;
import java.util.Map;

/**
 * 轻量健康检查接口。
 */
@RestController
@RequestMapping("/fastflow/api/v1")
public class HealthController {

    @GetMapping("/health")
    public Map<String, Object> health() {
        return Map.of(
                "status", "UP",
                "service", "FastFlow-API",
                "timestamp", Instant.now().toString()
        );
    }
}

package com.example;

import org.json.JSONObject;

public class Main {
    public static void main(String[] args) {
        JSONObject message = new JSONObject();
        message.put("greeting", "Hello");
        message.put("target", "World");
        message.put("runtime", "Docker");

        System.out.println("--- Java Hello World ---");
        System.out.println(message.toString(2));
    }
}

// ==============================================================
// Vitis HLS - High-Level Synthesis from C, C++ and OpenCL v2026.1 (64-bit)
// Tool Version Limit: 2026.06
// Copyright 1986-2022 Xilinx, Inc. All Rights Reserved.
// Copyright 2022-2026 Advanced Micro Devices, Inc. All Rights Reserved.
// 
// ==============================================================
/***************************** Include Files *********************************/
#include "xgemm_top.h"

/************************** Function Implementation *************************/
#ifndef __linux__
int XGemm_top_CfgInitialize(XGemm_top *InstancePtr, XGemm_top_Config *ConfigPtr) {
    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(ConfigPtr != NULL);

    InstancePtr->Ctrl_bus_BaseAddress = ConfigPtr->Ctrl_bus_BaseAddress;
    InstancePtr->IsReady = XIL_COMPONENT_IS_READY;

    return XST_SUCCESS;
}
#endif

void XGemm_top_Start(XGemm_top *InstancePtr) {
    u32 Data;

    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XGemm_top_ReadReg(InstancePtr->Ctrl_bus_BaseAddress, XGEMM_TOP_CTRL_BUS_ADDR_AP_CTRL) & 0x80;
    XGemm_top_WriteReg(InstancePtr->Ctrl_bus_BaseAddress, XGEMM_TOP_CTRL_BUS_ADDR_AP_CTRL, Data | 0x01);
}

u32 XGemm_top_IsDone(XGemm_top *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XGemm_top_ReadReg(InstancePtr->Ctrl_bus_BaseAddress, XGEMM_TOP_CTRL_BUS_ADDR_AP_CTRL);
    return (Data >> 1) & 0x1;
}

u32 XGemm_top_IsIdle(XGemm_top *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XGemm_top_ReadReg(InstancePtr->Ctrl_bus_BaseAddress, XGEMM_TOP_CTRL_BUS_ADDR_AP_CTRL);
    return (Data >> 2) & 0x1;
}

u32 XGemm_top_IsReady(XGemm_top *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XGemm_top_ReadReg(InstancePtr->Ctrl_bus_BaseAddress, XGEMM_TOP_CTRL_BUS_ADDR_AP_CTRL);
    // check ap_start to see if the pcore is ready for next input
    return !(Data & 0x1);
}

void XGemm_top_EnableAutoRestart(XGemm_top *InstancePtr) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XGemm_top_WriteReg(InstancePtr->Ctrl_bus_BaseAddress, XGEMM_TOP_CTRL_BUS_ADDR_AP_CTRL, 0x80);
}

void XGemm_top_DisableAutoRestart(XGemm_top *InstancePtr) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XGemm_top_WriteReg(InstancePtr->Ctrl_bus_BaseAddress, XGEMM_TOP_CTRL_BUS_ADDR_AP_CTRL, 0);
}

void XGemm_top_Set_M(XGemm_top *InstancePtr, u32 Data) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XGemm_top_WriteReg(InstancePtr->Ctrl_bus_BaseAddress, XGEMM_TOP_CTRL_BUS_ADDR_M_DATA, Data);
}

u32 XGemm_top_Get_M(XGemm_top *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XGemm_top_ReadReg(InstancePtr->Ctrl_bus_BaseAddress, XGEMM_TOP_CTRL_BUS_ADDR_M_DATA);
    return Data;
}

void XGemm_top_Set_K(XGemm_top *InstancePtr, u32 Data) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XGemm_top_WriteReg(InstancePtr->Ctrl_bus_BaseAddress, XGEMM_TOP_CTRL_BUS_ADDR_K_DATA, Data);
}

u32 XGemm_top_Get_K(XGemm_top *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XGemm_top_ReadReg(InstancePtr->Ctrl_bus_BaseAddress, XGEMM_TOP_CTRL_BUS_ADDR_K_DATA);
    return Data;
}

void XGemm_top_Set_N(XGemm_top *InstancePtr, u32 Data) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XGemm_top_WriteReg(InstancePtr->Ctrl_bus_BaseAddress, XGEMM_TOP_CTRL_BUS_ADDR_N_DATA, Data);
}

u32 XGemm_top_Get_N(XGemm_top *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XGemm_top_ReadReg(InstancePtr->Ctrl_bus_BaseAddress, XGEMM_TOP_CTRL_BUS_ADDR_N_DATA);
    return Data;
}

void XGemm_top_InterruptGlobalEnable(XGemm_top *InstancePtr) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XGemm_top_WriteReg(InstancePtr->Ctrl_bus_BaseAddress, XGEMM_TOP_CTRL_BUS_ADDR_GIE, 1);
}

void XGemm_top_InterruptGlobalDisable(XGemm_top *InstancePtr) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XGemm_top_WriteReg(InstancePtr->Ctrl_bus_BaseAddress, XGEMM_TOP_CTRL_BUS_ADDR_GIE, 0);
}

void XGemm_top_InterruptEnable(XGemm_top *InstancePtr, u32 Mask) {
    u32 Register;

    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Register =  XGemm_top_ReadReg(InstancePtr->Ctrl_bus_BaseAddress, XGEMM_TOP_CTRL_BUS_ADDR_IER);
    XGemm_top_WriteReg(InstancePtr->Ctrl_bus_BaseAddress, XGEMM_TOP_CTRL_BUS_ADDR_IER, Register | Mask);
}

void XGemm_top_InterruptDisable(XGemm_top *InstancePtr, u32 Mask) {
    u32 Register;

    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Register =  XGemm_top_ReadReg(InstancePtr->Ctrl_bus_BaseAddress, XGEMM_TOP_CTRL_BUS_ADDR_IER);
    XGemm_top_WriteReg(InstancePtr->Ctrl_bus_BaseAddress, XGEMM_TOP_CTRL_BUS_ADDR_IER, Register & (~Mask));
}

void XGemm_top_InterruptClear(XGemm_top *InstancePtr, u32 Mask) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XGemm_top_WriteReg(InstancePtr->Ctrl_bus_BaseAddress, XGEMM_TOP_CTRL_BUS_ADDR_ISR, Mask);
}

u32 XGemm_top_InterruptGetEnabled(XGemm_top *InstancePtr) {
    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    return XGemm_top_ReadReg(InstancePtr->Ctrl_bus_BaseAddress, XGEMM_TOP_CTRL_BUS_ADDR_IER);
}

u32 XGemm_top_InterruptGetStatus(XGemm_top *InstancePtr) {
    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    return XGemm_top_ReadReg(InstancePtr->Ctrl_bus_BaseAddress, XGEMM_TOP_CTRL_BUS_ADDR_ISR);
}


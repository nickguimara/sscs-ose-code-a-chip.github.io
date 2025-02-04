from glayout.flow.pdk.mappedpdk import MappedPDK
from glayout.flow.pdk.sky130_mapped import sky130_mapped_pdk
from gdsfactory.component import Component
from gdsfactory.cell import cell
from gdsfactory import Component
from gdsfactory.components import text_freetype, rectangle
from glayout.flow.primitives.fet import nmos, pmos, multiplier
from glayout.flow.pdk.util.comp_utils import evaluate_bbox, prec_center, align_comp_to_port, prec_ref_center
from glayout.flow.pdk.util.snap_to_grid import component_snap_to_grid
from glayout.flow.pdk.util.port_utils import rename_ports_by_orientation
from glayout.flow.routing.straight_route import straight_route
from glayout.flow.routing.c_route import c_route
from glayout.flow.routing.L_route import L_route
from glayout.flow.primitives.guardring import tapring
from glayout.flow.pdk.util.port_utils import add_ports_perimeter
from glayout.flow.spice.netlist import Netlist
from fvf import fvf_netlist, flipped_voltage_follower
from glayout.flow.primitives.via_gen import via_stack
from typing import Optional
"""
def low_voltage_cmirr_netlist(bias_fvf: Component, cascode_fvf: Component, fet_1A: Component, fet_1B: Component, fet_2A: Component, fet_2B: Component) -> Netlist:

        netlist = Netlist(circuit_name='Low_voltage_current_mirror', nodes=['IBIAS1', 'IBIAS2', 'GND', 'IOUT1', 'IOUT2'])
        netlist.connect_netlist(bias_fvf.info['netlist'], [('VIN','IBIAS1'),('VBULK','GND'),('Ib','IBIAS1')])
        netlist.connect_netlist(cascode_fvf.info['netlist'], [('VIN','IBIAS1'),('VBULK','GND'),('Ib', 'IBIAS2')])
        fet_1A_ref=netlist.connect_netlist(fet_1A.info['netlist'], [('D', 'IOUT1'),('G','IBIAS1'),('B','GND')])
        fet_2A_ref=netlist.connect_netlist(fet_2A.info['netlist'], [('D', 'IOUT2'),('G','IBIAS1'),('B','GND')])
        fet_1B_ref=netlist.connect_netlist(fet_1B.info['netlist'], [('G','IBIAS2'),('S', 'GND'),('B','GND')])
        fet_2B_ref=netlist.connect_netlist(fet_2B.info['netlist'], [('G','IBIAS2'),('S', 'GND'),('B','GND')])
        netlist.connect_subnets(
                fet_1A_ref,
                fet_1B_ref,
                [('S', 'D')]
                )
        netlist.connect_subnets(
                fet_2A_ref,
                fet_2B_ref,
                [('S', 'D')]
                )

        return netlist
"""
def sky130_add_lvcm_labels(lvcm_in: Component) -> Component:
	
    lvcm_in.unlock()
    # define layers`
    met1_pin = (68,16)
    met1_label = (68,5)
    met2_pin = (69,16)
    met2_label = (69,5)
    # list that will contain all port/comp info
    move_info = list()
    # create labels and append to info list
    # gnd
    gndlabel = rectangle(layer=met1_pin,size=(0.5,0.5),centered=True).copy()
    gndlabel.add_label(text="VBULK",layer=met1_label)
    move_info.append((gndlabel,lvcm_in.ports["M_3_B_tie_N_top_met_N"],None))
    
    #currentinput
    ibias1label = rectangle(layer=met2_pin,size=(0.5,0.5),centered=True).copy()
    ibias1label.add_label(text="IBIAS1",layer=met2_label)
    move_info.append((ibias1label,lvcm_in.ports["M_1_A_drain_top_met_N"],None))
    ibias2label = rectangle(layer=met2_pin,size=(0.5,0.5),centered=True).copy()
    ibias2label.add_label(text="IBIAS2",layer=met2_label)
    move_info.append((ibias2label,lvcm_in.ports["M_2_A_drain_top_met_N"],None))
    
    # currentoutput
    iout1label = rectangle(layer=met1_pin,size=(0.25,0.25),centered=True).copy()
    iout1label.add_label(text="IOUT1",layer=met1_label)
    move_info.append((iout1label,lvcm_in.ports["M_3_A_multiplier_0_drain_N"],None))
    
    iout2label = rectangle(layer=met1_pin,size=(0.25,0.25),centered=True).copy()
    iout2label.add_label(text="IOUT2",layer=met1_label)
    move_info.append((iout2label,lvcm_in.ports["M_4_A_multiplier_0_drain_N"],None))
    
    # move everything to position
    for comp, prt, alignment in move_info:
        alignment = ('c','b') if alignment is None else alignment
        compref = align_comp_to_port(comp, prt, alignment=alignment)
        lvcm_in.add(compref)
    return lvcm_in.flatten() 

@cell
def  low_voltage_cmirror(
        pdk: MappedPDK,
        width:  tuple[float,float] = (4.15,1.42),
        length: float = 2,
        fingers: tuple[int,int] = (2,1),
        multipliers: tuple[int,int] = (1,1),
        ) -> Component:
    """
    A low voltage N type current mirror
    """
    #top level component
    top_level = Component("Low_voltage_N-type_current_mirror")

    #input branch 2
    cascode_fvf = flipped_voltage_follower(pdk, width=(width[0],width[0]), length=(length,length), fingers=(fingers[0],fingers[0]), multipliers=(multipliers[0],multipliers[0]))
    cascode_fvf_ref = prec_ref_center(cascode_fvf)
    top_level.add(cascode_fvf_ref)
    
    #input branch 1
    bias_fvf = flipped_voltage_follower(pdk, width=(width[0],width[1]), length=(length,length), fingers=(fingers[0],fingers[1]), multipliers=(multipliers[0],multipliers[1]), placement="vertical")
    bias_fvf_ref = prec_ref_center(bias_fvf,(0,-18))
    top_level.add(bias_fvf_ref)

    #creating fets for output branches
    fet_1 = nmos(pdk, width=width[0], fingers=fingers[0], multipliers=multipliers[0], with_dummy=True, with_dnwell=False,  with_substrate_tap=False, length=length)
    fet_1_ref = prec_ref_center(fet_1,(-23,0))
    fet_2_ref =prec_ref_center(fet_1,(-38,0)) 
    fet_3_ref =prec_ref_center(fet_1,(23,0))
    fet_4_ref =prec_ref_center(fet_1,(38,0))
    top_level.add(fet_1_ref)
    top_level.add(fet_2_ref)
    top_level.add(fet_3_ref)
    top_level.add(fet_4_ref)
 
    top_level << c_route(pdk, bias_fvf_ref.ports["A_multiplier_0_gate_E"], bias_fvf_ref.ports["B_gate_bottom_met_E"])
    top_level << c_route(pdk, cascode_fvf_ref.ports["A_multiplier_0_gate_W"], bias_fvf_ref.ports["A_multiplier_0_gate_W"])
    top_level << straight_route(pdk, cascode_fvf_ref.ports["B_gate_bottom_met_E"], fet_3_ref.ports["multiplier_0_gate_W"])
    
    #creating vias for routing
    viam2m3 = via_stack(pdk, "met2", "met3", centered=True)
    gate_1_via = top_level << viam2m3 
    gate_1_via.move(fet_1_ref.ports["multiplier_0_gate_W"].center).movex(-1)
    gate_2_via = top_level << viam2m3                                         
    gate_2_via.move(fet_2_ref.ports["multiplier_0_gate_W"].center).movex(-1)
    gate_3_via = top_level << viam2m3 
    gate_3_via.move(fet_3_ref.ports["multiplier_0_gate_E"].center).movex(1)
    gate_4_via = top_level << viam2m3 
    gate_4_via.move(fet_4_ref.ports["multiplier_0_gate_E"].center).movex(1)

    source_2_via = top_level << viam2m3
    drain_1_via = top_level << viam2m3
    source_2_via.move(fet_2_ref.ports["multiplier_0_source_E"].center).movex(1.5)
    drain_1_via.move(fet_1_ref.ports["multiplier_0_drain_W"].center).movex(-1)

    source_4_via = top_level << viam2m3
    drain_3_via = top_level << viam2m3
    source_4_via.move(fet_4_ref.ports["multiplier_0_source_W"].center).movex(-1)
    drain_3_via.move(fet_3_ref.ports["multiplier_0_drain_E"].center).movex(1.5)
    
    #routing
    top_level << straight_route(pdk, fet_2_ref.ports["multiplier_0_source_E"], source_2_via.ports["bottom_met_W"])
    top_level << straight_route(pdk, fet_1_ref.ports["multiplier_0_drain_W"], drain_1_via.ports["bottom_met_E"])
    top_level << straight_route(pdk, fet_4_ref.ports["multiplier_0_source_W"], source_4_via.ports["bottom_met_E"])
    top_level << straight_route(pdk, fet_3_ref.ports["multiplier_0_drain_E"], drain_3_via.ports["bottom_met_W"])
    top_level << c_route(pdk, source_2_via.ports["top_met_N"], drain_1_via.ports["top_met_N"], extension=1.5, width1=0.32, width2=0.32, cwidth=0.32, e1glayer="met3", e2glayer="met3", cglayer="met2")
    top_level << c_route(pdk, source_4_via.ports["top_met_N"], drain_3_via.ports["top_met_N"], extension=1.5, width1=0.32, width2=0.32, cwidth=0.32, e1glayer="met3", e2glayer="met3", cglayer="met2")
    top_level << c_route(pdk, bias_fvf_ref.ports["A_multiplier_0_gate_E"], gate_4_via.ports["bottom_met_E"], width1=0.32, width2=0.32, cwidth=0.32) 

 
    top_level << straight_route(pdk, fet_1_ref.ports["multiplier_0_gate_W"], gate_1_via.ports["bottom_met_E"])
    top_level << straight_route(pdk, fet_2_ref.ports["multiplier_0_gate_W"], gate_2_via.ports["bottom_met_E"])    
    top_level << straight_route(pdk, fet_3_ref.ports["multiplier_0_gate_E"], gate_3_via.ports["bottom_met_W"])
    top_level << straight_route(pdk, fet_4_ref.ports["multiplier_0_gate_E"], gate_4_via.ports["bottom_met_W"])

    top_level << c_route(pdk, gate_1_via.ports["top_met_S"], gate_3_via.ports["top_met_S"], extension=1.9, cglayer='met2')
    top_level << c_route(pdk, gate_2_via.ports["top_met_S"], gate_4_via.ports["top_met_S"], extension=3.2, cglayer='met2')
    
    top_level << straight_route(pdk, fet_1_ref.ports["multiplier_0_source_W"], fet_1_ref.ports["tie_W_top_met_W"], glayer1='met1', width=0.2)
    top_level << straight_route(pdk, fet_3_ref.ports["multiplier_0_source_W"], fet_3_ref.ports["tie_W_top_met_W"], glayer1='met1', width=0.2)
    
    #adding a pwell
    top_level.add_padding(layers=(pdk.get_glayer("pwell"),),default=pdk.get_grule("pwell", "active_tap")["min_enclosure"], ) 

    top_level.add_ports(bias_fvf_ref.get_ports_list(), prefix="M_1_")
    top_level.add_ports(cascode_fvf_ref.get_ports_list(), prefix="M_2_")
    top_level.add_ports(fet_1_ref.get_ports_list(), prefix="M_3_B_")
    top_level.add_ports(fet_2_ref.get_ports_list(), prefix="M_3_A_")
    top_level.add_ports(fet_3_ref.get_ports_list(), prefix="M_4_B_")
    top_level.add_ports(fet_4_ref.get_ports_list(), prefix="M_4_A_")
    
    #for netlist
    fet_1A = nmos(pdk, width=width[0], fingers=fingers[0], multipliers=multipliers[0], with_dummy=True, with_dnwell=False,  with_substrate_tap=False, length=length)
    fet_1B = nmos(pdk, width=width[0], fingers=fingers[0], multipliers=multipliers[0], with_dummy=True, with_dnwell=False,  with_substrate_tap=False, length=length)
    fet_2A = nmos(pdk, width=width[0], fingers=fingers[0], multipliers=multipliers[0], with_dummy=True, with_dnwell=False,  with_substrate_tap=False, length=length)
    fet_2B = nmos(pdk, width=width[0], fingers=fingers[0], multipliers=multipliers[0], with_dummy=True, with_dnwell=False,  with_substrate_tap=False, length=length)
    #top_level.info['netlist'] = low_voltage_cmirr_netlist(bias_fvf, cascode_fvf, fet_1A, fet_1B, fet_2A, fet_2B)
    
    #print(top_level.info['netlist'].generate_netlist(only_subcircuits=True))
    
    
    return component_snap_to_grid(rename_ports_by_orientation(top_level))
"""
lvcm = sky130_add_lvcm_labels(low_voltage_cmirror(sky130_mapped_pdk))
lvcm.show()
lvcm.name = "lvcm"
magic_drc_result = sky130_mapped_pdk.drc_magic(lvcm, lvcm.name)
netgen_lvs_result = sky130_mapped_pdk.lvs_netgen(lvcm, lvcm.name, netlist="lvcm.spice")
"""
